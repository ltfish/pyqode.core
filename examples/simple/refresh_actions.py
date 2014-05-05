#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This example is an alternative version of style_and_settings where we modify
the settings and styles after CodeEdit has been shown.

"""
import sys

from PyQt4 import QtGui

from pyqode.core import frontend
from pyqode.core import actions
from pyqode.core.frontend import modes
from pyqode.core.frontend import panels


def main():
    app = QtGui.QApplication(sys.argv)
    window = QtGui.QMainWindow()

    # code from the simple example
    editor = frontend.CodeEdit()
    frontend.open_file(editor, __file__)
    frontend.install_mode(editor, modes.CaretLineHighlighterMode())
    frontend.install_mode(editor, modes.PygmentsSyntaxHighlighter(
        editor.document()))
    frontend.install_panel(
        editor, panels.SearchAndReplacePanel(),
        position=panels.SearchAndReplacePanel.Position.TOP)
    window.setCentralWidget(editor)
    window.show()

    actions.redo.shortcut = 'Ctrl+Y'
    editor.refresh_actions()
    app.exec_()

    del editor
    del window
    del app


if __name__ == "__main__":
    main()




