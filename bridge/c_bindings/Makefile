# DBAI Hardware Interrupt C-Bindings Makefile

CC = gcc
CFLAGS = -Wall -Wextra -O2 -fPIC -std=c11
LDFLAGS = -shared
TARGET = libhw_interrupts.so

SOURCES = hw_interrupts.c
OBJECTS = $(SOURCES:.c=.o)

.PHONY: all clean test

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c hw_interrupts.h
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJECTS) $(TARGET)

test: $(TARGET)
	@echo "=== Bibliothek erstellt ==="
	@ls -la $(TARGET)
	@echo "=== Symbole ==="
	@nm -D $(TARGET) | grep " T "

install: $(TARGET)
	cp $(TARGET) ../../lib/
