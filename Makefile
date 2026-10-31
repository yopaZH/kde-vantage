.PHONY: install uninstall

install:
	chmod +x ./install.sh
	./install.sh
	install -D -o root -g root -m 755 ./vantage.py /usr/bin/vantage
	install -D -o root -g root -m 755 ./vantage-bind-key /usr/bin/vantage-bind-key
	install -D -o root -g root -m 755 ./vantage-helper /usr/lib/vantage/vantage-helper
	install -D -o root -g root -m 644 ./org.vantage.helper.policy /usr/share/polkit-1/actions/org.vantage.helper.policy
	install -D -o root -g root -m 644 ./icon.png /usr/share/icons/hicolor/scalable/apps/vantage.png
	install -D -o root -g root -m 644 ./vantage.desktop /usr/share/applications/vantage.desktop

uninstall:
	rm -f /usr/bin/vantage
	rm -f /usr/bin/vantage-bind-key
	rm -f /usr/lib/vantage/vantage-helper
	rmdir --ignore-fail-on-non-empty /usr/lib/vantage 2>/dev/null || true
	rm -f /usr/share/polkit-1/actions/org.vantage.helper.policy
	rm -f /usr/share/icons/hicolor/scalable/apps/vantage.png
	rm -f /usr/share/applications/vantage.desktop
