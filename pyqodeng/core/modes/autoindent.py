# -*- coding: utf-8 -*-
""" Contains the automatic generic indenter """
from pyqodeng.core.api import TextHelper
from pyqodeng.core.api.mode import Mode
from qtpy.QtCore import Qt


class AutoIndentMode(Mode):
    """ Indents text automatically.
    Generic indenter mode that indents the text when the user press RETURN.

    You can customize this mode by overriding
    :meth:`pyqode.core.modes.AutoIndentMode._get_indent`
    """
    def __init__(self):
        super(AutoIndentMode, self).__init__()

    @property
    def _indent_char(self):

        if self.editor.use_spaces_instead_of_tabs:
            return ' '
        return '\t'

    @property
    def _single_indent(self):

        if self.editor.use_spaces_instead_of_tabs:
            return self.editor.tab_length * ' '
        return '\t'

    def _get_indent(self, cursor):
        """
        Return the indentation text (a series of spaces or tabs)

        :param cursor: QTextCursor

        :returns: Tuple (text before new line, text after new line)
        """
        indent = TextHelper(self.editor).line_indent() * self._indent_char
        return "", indent

    def on_state_changed(self, state):
        if state is True:
            self.editor.key_pressed.connect(self._on_key_pressed)
        else:
            self.editor.key_pressed.disconnect(self._on_key_pressed)

    def _on_key_pressed(self, event):
        """
        Auto indent if the released key is the return key.
        :param event: the key event
        """
        if not event.isAccepted() and (event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter):
            cursor = self.editor.textCursor()
            pre, post = self._get_indent(cursor)
            cursor.beginEditBlock()
            cursor.insertText(f"{pre}\n{post}")
            cursor.endEditBlock()
            event.accept()
