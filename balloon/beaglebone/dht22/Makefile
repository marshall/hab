BBB_KDIR := /home/marshall/Source/bbb-kernel/kernel
obj-m := dht22.o

PWD=$(shell pwd)

default:
	$(MAKE) ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- -C $(BBB_KDIR) M=$(PWD) modules

.PHONY: clean
clean:
	$(MAKE) ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- -C $(BBB_KDIR) M=$(PWD) clean
