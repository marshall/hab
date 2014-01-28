/*
 *  dht22.c
 *
 * A port of the DHT11 driver to linux kernel 3.8, based on sysfs rather than IIO
 *
 *  Copyright (C) 2014 by Marshall Culpepper
 */

#define LINUX

#include <linux/completion.h>
#include <linux/delay.h>
#include <linux/err.h>
#include <linux/gpio.h>
#include <linux/hwmon.h>
#include <linux/hwmon-sysfs.h>
#include <linux/interrupt.h>
#include <linux/jiffies.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/platform_device.h>

#include "dht22.h"

#define DRIVER_NAME "dht22"

#define DHT22_DATA_VALID_TIME   2000000000  /* 2s in ns */

#define DHT22_EDGES_PREAMBLE 4
#define DHT22_BITS_PER_READ 40
#define DHT22_EDGES_PER_READ (2*DHT22_BITS_PER_READ + DHT22_EDGES_PREAMBLE + 1)

/* Data transmission timing (nano seconds) */
#define DHT22_START_TRANSMISSION    18  /* ms */
#define DHT22_SENSOR_RESPONSE   80000
#define DHT22_START_BIT     50000
#define DHT22_DATA_BIT_LOW  27000
#define DHT22_DATA_BIT_HIGH 70000

#define GPIO_P8_12 44
#define DHT22_DTA GPIO_P8_12

enum { dht22_id };

struct dht22 {
    struct device *dev;
    struct device *hwmon_dev;

    int gpio;
    int irq;
    struct completion completion;
    ktime_t timestamp;
    int temperature;
    int humidity;

    /* num_edges: -1 means "no transmission in progress" */
    int num_edges;
    struct {ktime_t ts; int value; }    edges[DHT22_EDGES_PER_READ];
};

static inline void reinit_completion(struct completion *x) {
   x->done = 0;
}

static unsigned char dht22_decode_byte(int *timing, int threshold)
{
    unsigned char ret = 0;
    int i;

    for (i = 0; i < 8; ++i) {
        ret <<= 1;
        if (timing[i] >= threshold)
            ++ret;
    }

    return ret;
}

static int dht22_decode(struct dht22 *dht22, int offset)
{
    int i, t, timing[DHT22_BITS_PER_READ], threshold,
        timeres = DHT22_SENSOR_RESPONSE;
    unsigned char temp_int, temp_dec, hum_int, hum_dec, checksum;

    /* Calculate timestamp resolution */
    for (i = 0; i < dht22->num_edges; ++i) {
        t = ktime_to_ns(ktime_sub(dht22->edges[i].ts, dht22->edges[i-1].ts));
        if (t > 0 && t < timeres)
            timeres = t;
    }
    if (2*timeres > DHT22_DATA_BIT_HIGH) {
        pr_err("dht22: timeresolution %d too bad for decoding\n",
            timeres);
        return -EIO;
    }
    threshold = DHT22_DATA_BIT_HIGH / timeres;
    if (DHT22_DATA_BIT_LOW/timeres + 1 >= threshold)
        pr_err("dht22: WARNING: decoding ambiguous\n");

    /* scale down with timeres and check validity */
    for (i = 0; i < DHT22_BITS_PER_READ; ++i) {
        t = ktime_to_ns(ktime_sub(dht22->edges[offset + 2*i + 2].ts,
                                  dht22->edges[offset + 2*i + 1].ts));
        if (!dht22->edges[offset + 2*i + 1].value)
            return -EIO;  /* lost synchronisation */
        timing[i] = t / timeres;
    }

    hum_int = dht22_decode_byte(timing, threshold);
    hum_dec = dht22_decode_byte(&timing[8], threshold);
    temp_int = dht22_decode_byte(&timing[16], threshold);
    temp_dec = dht22_decode_byte(&timing[24], threshold);
    checksum = dht22_decode_byte(&timing[32], threshold);

    if (((hum_int + hum_dec + temp_int + temp_dec) & 0xff) != checksum)
        return -EIO;

    dht22->timestamp = ktime_get();
    if (hum_int < 20) {  /* DHT22 */
        dht22->temperature = (((temp_int & 0x7f) << 8) + temp_dec) *
                    ((temp_int & 0x80) ? -100 : 100);
        dht22->humidity = ((hum_int << 8) + hum_dec) * 100;
    } else if (temp_dec == 0 && hum_dec == 0) {  /* dht22 */
        dht22->temperature = temp_int * 1000;
        dht22->humidity = hum_int * 1000;
    } else {
        dev_err(dht22->dev,
            "Don't know how to decode data: %d %d %d %d\n",
            hum_int, hum_dec, temp_int, temp_dec);
        return -EIO;
    }

    return 0;
}

static int dht22_update_measurement(struct dht22 *dht22)
{
    int ret;

    if (ktime_to_ns(dht22->timestamp) + DHT22_DATA_VALID_TIME < ktime_to_ns(ktime_get())) {
        reinit_completion(&dht22->completion);

        dht22->num_edges = 0;
        ret = gpio_direction_output(dht22->gpio, 0);
        if (ret)
            goto err;
        msleep(DHT22_START_TRANSMISSION);
        ret = gpio_direction_input(dht22->gpio);
        if (ret)
            goto err;

        ret = wait_for_completion_killable_timeout(&dht22->completion,
                                 HZ);
        if (ret == 0 && dht22->num_edges < DHT22_EDGES_PER_READ - 1) {
            dev_err(dht22->dev,
                    "Only %d signal edges detected\n",
                    dht22->num_edges);
            ret = -ETIMEDOUT;
        }
        if (ret < 0)
            goto err;

        ret = dht22_decode(dht22,
                dht22->num_edges == DHT22_EDGES_PER_READ ?
                    DHT22_EDGES_PREAMBLE :
                    DHT22_EDGES_PREAMBLE - 2);
        if (ret)
            goto err;
    }

    return 0;

err:
    dht22->num_edges = -1;
    return ret;
}

static irqreturn_t dht22_handle_irq(int irq, void *data)
{
    struct dht22 *dht22 = data;

    /* TODO: Consider making the handler safe for IRQ sharing */
    if (dht22->num_edges < DHT22_EDGES_PER_READ && dht22->num_edges >= 0) {
        dht22->edges[dht22->num_edges].ts = ktime_get();
        dht22->edges[dht22->num_edges++].value = gpio_get_value(dht22->gpio);

        if (dht22->num_edges >= DHT22_EDGES_PER_READ)
            complete(&dht22->completion);
    }

    return IRQ_HANDLED;
}

static ssize_t dht22_show_temp(struct device *dev,
                               struct device_attribute *attr,
                               char *buf)
{
    int ret;
    struct dht22 *dht22 = dev_get_drvdata(dev);

    /* Technically no need to read humidity as well */
    ret = dht22_update_measurement(dht22);
    if (ret) {
        return ret;
    }

    return sprintf(buf, "%d\n", dht22->temperature);
}

static ssize_t dht22_show_humidity(struct device *dev,
                                   struct device_attribute *attr,
                                   char *buf)
{
    int ret;
    struct dht22 *dht22 = dev_get_drvdata(dev);

    ret = dht22_update_measurement(dht22);
    if (ret) {
        return ret;
    }

    return sprintf(buf, "%d\n", dht22->humidity);
}

static SENSOR_DEVICE_ATTR(temp, S_IRUGO, dht22_show_temp, NULL, 0);
static SENSOR_DEVICE_ATTR(humidity, S_IRUGO, dht22_show_humidity, NULL, 0);
static struct attribute *dht22_attrs[] = {
    &sensor_dev_attr_temp.dev_attr.attr,
    &sensor_dev_attr_humidity.dev_attr.attr,
    NULL,
};

static const struct attribute_group dht22_attr_group = {
    .attrs = dht22_attrs,
};

static int dht22_probe(struct platform_device *pdev) {
    int ret;
    struct dht22 *data;

    data = devm_kzalloc(&pdev->dev, sizeof(*data), GFP_KERNEL);
    if (!data)
        return -ENOMEM;

    data->gpio= DHT22_DTA;
    data->dev = &pdev->dev;
    /*if (pdev->dev.platform_data == NULL) {
        dev_err(&pdev->dev, "no platform data supplied\n");
        return -EINVAL;
    }

    data->pdata = pdev->dev.platform_data;*/
    ret = devm_gpio_request_one(&pdev->dev, data->gpio, GPIOF_IN, pdev->name);
    if (ret) {
        dev_err(&pdev->dev, "gpio output request failed\n");
        goto err;
    }

    data->irq = gpio_to_irq(data->gpio);
    if (data->irq < 0) {
        dev_err(&pdev->dev, "GPIO %d has no interrupt\n", data->gpio);
        return -EINVAL;
    }

    ret = devm_request_irq(&pdev->dev, data->irq, dht22_handle_irq,
                           IRQF_TRIGGER_RISING | IRQF_TRIGGER_FALLING,
                           pdev->name, data);
    if (ret) {
        dev_err(&pdev->dev, "Failed to request IRQ\n");
        return ret;
    }

    data->timestamp = ktime_sub_ns(ktime_get(), DHT22_DATA_VALID_TIME - 1);
    data->num_edges = -1;
    platform_set_drvdata(pdev, data);
    init_completion(&data->completion);


    ret = sysfs_create_group(&pdev->dev.kobj, &dht22_attr_group);
    if (ret) {
        dev_err(&pdev->dev, "sysfs create failed\n");
        goto err;
    }

    data->hwmon_dev = hwmon_device_register(data->dev);
    if (IS_ERR(data->hwmon_dev)) {
        ret = PTR_ERR(data->hwmon_dev);
        goto err_release_sysfs_group;
    }

    return 0;

err_release_sysfs_group:
    sysfs_remove_group(&pdev->dev.kobj, &dht22_attr_group);
err:
    return ret;
}

static int dht22_remove(struct platform_device *pdev) {
    struct dht22 *data = platform_get_drvdata(pdev);

    devm_gpio_free(&pdev->dev, data->gpio);
    hwmon_device_unregister(data->hwmon_dev);
    sysfs_remove_group(&pdev->dev.kobj, &dht22_attr_group);
    return 0;
}

static struct platform_device_id dht22_device_ids[] = {
    { "dht22", dht22_id },
    { }
};
MODULE_DEVICE_TABLE(platform, dht22_device_ids);

static struct platform_driver dht22_driver = {
    .driver = {
        .name = "dht22",
        .owner = THIS_MODULE,
    },
    .probe = dht22_probe,
    .remove = dht22_remove,
    .id_table = dht22_device_ids,
};

static struct dht22_platform_data platform_data_dht22 = {
    .gpio_data =  DHT22_DTA,
};

static struct platform_device dht22_device = {
    .name = "dht22",
    .id = -1,
    .dev = {
        .platform_data = &platform_data_dht22,
    },
};

static struct platform_device *dht22_devices[] = {
    &dht22_device,
};

static int __init dht22_init(void) {
    int ret;

    ret = platform_driver_register(&dht22_driver);
    if (ret) {
        platform_driver_unregister(&dht22_driver);
        return ret;
    }

    platform_add_devices(dht22_devices, ARRAY_SIZE(dht22_devices));
    return 0;
}
module_init(dht22_init);

static void __exit dht22_exit(void) {
    platform_driver_unregister(&dht22_driver);
}
module_exit(dht22_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("DHT22 temperature and humidity sensor driver");
