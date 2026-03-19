CC=gcc
CFLAGS=-shared -fPIC

all: c_src/pcb.so

c_src/pcb.so: c_src/pcb.c
	$(CC) $(CFLAGS) -o c_src/pcb.so c_src/pcb.c

test:
	pytest tests/ -v

clean:
	rm -f c_src/pcb.so
