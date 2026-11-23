# SPDX-License-Identifier: ISC
PREFIX ?= /usr/local
DISPATCHER = /etc/NetworkManager/dispatcher.d

all:
	@echo "Use 'sudo make install' to install to $(PREFIX) and set up a NetworkManager dispatcher."

# NM only scans dispatcher.d/; a symlink into no-wait.d/ makes it no-wait.
install:
	install -m 0755 uncaptive $(PREFIX)/bin/uncaptive
	install -m 0755 -o root -g root 90-uncaptive $(DISPATCHER)/no-wait.d/90-uncaptive
	ln -sf no-wait.d/90-uncaptive $(DISPATCHER)/90-uncaptive

uninstall:
	rm -f $(PREFIX)/bin/uncaptive $(DISPATCHER)/90-uncaptive \
		$(DISPATCHER)/no-wait.d/90-uncaptive

check:
	python3 test/fake-portal.py

.PHONY: install uninstall check
