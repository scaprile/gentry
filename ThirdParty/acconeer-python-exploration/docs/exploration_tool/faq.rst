FAQ and common issues
=====================

Python related
--------------

#) Import errors with NumPy on Linux

   The solution is to remove all duplicates of NumPy and reinstall using pip::

      sudo apt remove python3-numpy
      python -m pip uninstall numpy       # Repeat until no NumPy version is installed
      python -m pip install --user numpy

   Depending on your environment, you might have to replace ``python`` with ``python3`` or ``py``.

#) The GUI does not load properly after updating

   Try running ``python -m acconeer.exptool.app --purge-config`` from anywhere. Accept the
   removal of the files and try starting Exploration Tool again.

   If the above does not work, please open an issue on GitHub.

#) The GUI does not start and shows an error: ``qt.qpa.plugin: Could not find the Qt platform plugin "windows" in ""``.

   This error may occur when there are non-ASCII characters in the path.

#) Dropdown menu is out of position

   This is a known issue on for Qt when running Wayland display server. The issue is fixed for Qt verison >= 6.4.0.
   (See related issue: https://bugreports.qt.io/browse/QTBUG-85297)

Sensor related
--------------

#) What does "Experimental" mean?

   In our code you might encounter features tagged “experimental”. This means that the feature in question is an early version that has a limited test scope, and the API and/or functionality might change in upcoming releases. The intention is to let users try these features out and we appreciate feedback.
