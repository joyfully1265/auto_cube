"""Widgets for building the AND/OR tree of desired stat lines.

A ``LogicGroup`` is a frame holding rows and nested groups.  Each
``ConditionRow`` is one desired line (``stat value``, e.g. ``STR 12``) plus
``+``/up/down/remove buttons.  Rows of an AND group are contributions: their
values are summed per stat, so ``STR 12`` and ``STR 9`` mean ``STR >= 21%``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional, Sequence, Union

from ..modes.cube.logic_goal import AND, OR, DesiredLine, GroupNode


class ConditionRow(ttk.Frame):
    """One desired line with +, up, down and remove buttons."""

    def __init__(
        self,
        parent: tk.Widget,
        stats: Sequence[str],
        value_options: Callable[[str], Sequence[str]],
        on_add: Callable[["ConditionRow"], None],
        on_move: Callable[["ConditionRow", int], None],
        on_remove: Callable[["ConditionRow"], None],
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._value_options = value_options
        self._on_change = on_change

        self.stat = ttk.Combobox(self, values=stats, state="readonly", width=16)
        self.value = ttk.Combobox(self, state="readonly", width=8)

        self.columnconfigure(0, weight=1)
        self.stat.grid(row=0, column=0, sticky="ew")
        self.value.grid(row=0, column=1, padx=(8, 0))
        self._buttons = (
            ttk.Button(self, text="+", width=3, command=lambda: on_add(self)),
            ttk.Button(self, text="\u2191", width=3, command=lambda: on_move(self, -1)),
            ttk.Button(self, text="\u2193", width=3, command=lambda: on_move(self, 1)),
            ttk.Button(self, text="\u00d7", width=3, command=lambda: on_remove(self)),
        )
        for column, button in enumerate(self._buttons, start=2):
            button.grid(row=0, column=column, padx=(8 if column == 2 else 4, 0))

        if stats:
            self.stat.set(stats[0])
        self.stat.bind("<<ComboboxSelected>>", lambda _event: self._on_stat_changed())
        self.value.bind("<<ComboboxSelected>>", lambda _event: self._notify())
        self.refresh_values()

    def refresh_values(self) -> None:
        """Repopulate the value dropdown for the selected stat."""
        values = list(self._value_options(self.stat.get()))
        self.value.configure(values=values)
        self.value.set(values[0] if values else "")

    def _on_stat_changed(self) -> None:
        """Repopulate values for the newly selected stat, then report it."""
        self.refresh_values()
        self._notify()

    def _notify(self) -> None:
        """Tell the owning group that this row changed."""
        if self._on_change is not None:
            self._on_change()

    def set_stats(self, stats: Sequence[str]) -> None:
        """Replace the stat options, keeping the selection when possible."""
        self.stat.configure(values=stats)
        if self.stat.get() not in stats:
            self.stat.set(stats[0] if stats else "")
            self.refresh_values()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or lock this row's inputs."""
        box_state = "readonly" if enabled else "disabled"
        for box in (self.stat, self.value):
            box.configure(state=box_state)
        for button in self._buttons:
            button.configure(state="normal" if enabled else "disabled")

    def to_desired_line(self) -> Optional[DesiredLine]:
        """Return this row as a desired line, or None when incomplete."""
        digits = self.value.get().strip().rstrip("%")
        if not self.stat.get() or not digits.isdigit():
            return None
        return DesiredLine(self.stat.get(), int(digits))


class LogicGroup(ttk.Frame):
    """An AND/OR group holding desired lines and nested groups."""

    def __init__(
        self,
        parent: tk.Widget,
        stats_provider: Callable[[], Sequence[str]],
        value_options: Callable[[str], Sequence[str]],
        operator: str = AND,
        on_remove: Optional[Callable[["LogicGroup"], None]] = None,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent, relief="groove", borderwidth=2)
        self._stats_provider = stats_provider
        self._value_options = value_options
        self._on_remove = on_remove
        self._on_change = on_change
        self._items: List[tk.Widget] = []
        self._separators: List[ttk.Combobox] = []
        self._enabled = True
        # Shared by every separator: a group has a single AND/OR.  The
        # separators carry no <<ComboboxSelected>> binding, so the trace is the
        # only way a mode change reaches the owner.
        self.operator = tk.StringVar(self, operator)
        self.operator.trace_add("write", lambda *_: self._notify())

        self.columnconfigure(0, weight=1)

        header = ttk.Frame(self, padding=4)
        header.grid(row=0, column=0, sticky="ew")
        self._buttons: List[ttk.Button] = [
            ttk.Button(header, text="+ Group", command=self.add_group),
            ttk.Button(header, text="+", width=3, command=self.add_condition),
        ]
        if on_remove is not None:
            self._buttons.append(
                ttk.Button(
                    header, text="\u00d7", width=3, command=lambda: on_remove(self)
                )
            )
        for index, button in enumerate(self._buttons):
            button.pack(side="left", padx=(0 if index == 0 else 8, 0))

        # Left padding indents children under the group header.
        self.body = ttk.Frame(self, padding=(16, 4, 4, 4))
        self.body.grid(row=1, column=0, sticky="ew")
        self.body.columnconfigure(0, weight=1)

    # -- Public API -------------------------------------------------------

    def add_condition(self) -> ConditionRow:
        """Append a condition to the end of this group."""
        condition = self._create_condition()
        self._insert(condition)
        return condition

    def add_group(self) -> "LogicGroup":
        """Append a nested group to the end of this group."""
        group = LogicGroup(
            self.body,
            self._stats_provider,
            self._value_options,
            operator=OR,
            on_remove=self._remove,
            on_change=self._on_change,
        )
        group.set_enabled(self._enabled)
        self._insert(group)
        group.add_condition()
        return group

    def condition_rows(self) -> List[ConditionRow]:
        """Return every condition in this group, including nested groups."""
        rows: List[ConditionRow] = []
        for item in self._items:
            if isinstance(item, LogicGroup):
                rows.extend(item.condition_rows())
            else:
                rows.append(item)
        return rows

    def to_node(self) -> GroupNode:
        """Return this group and its children as a goal node."""
        items: List[Union[GroupNode, DesiredLine]] = []
        for item in self._items:
            node = (
                item.to_desired_line()
                if isinstance(item, ConditionRow)
                else item.to_node()
            )
            if node is not None:
                items.append(node)
        return GroupNode(self.operator.get(), items)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or lock this group and every child, including nested groups."""
        self._enabled = enabled
        for button in self._buttons:
            button.configure(state="normal" if enabled else "disabled")
        for separator in self._separators:
            separator.configure(state="readonly" if enabled else "disabled")
        for item in self._items:
            if isinstance(item, (ConditionRow, LogicGroup)):
                item.set_enabled(enabled)

    # -- Internals --------------------------------------------------------

    def _create_condition(self) -> ConditionRow:
        condition = ConditionRow(
            self.body,
            self._stats_provider(),
            self._value_options,
            self._add_after,
            self._move,
            self._remove,
            on_change=self._on_change,
        )
        condition.set_enabled(self._enabled)
        return condition

    def _notify(self) -> None:
        """Report a structural or value change to the owner."""
        if self._on_change is not None:
            self._on_change()

    def _remove(self, widget: tk.Widget) -> None:
        self._items.remove(widget)
        widget.destroy()
        self._relayout()
        self._notify()

    def _insert(self, widget: tk.Widget, after: Optional[tk.Widget] = None) -> None:
        index = (
            self._items.index(after) + 1 if after in self._items else len(self._items)
        )
        self._items.insert(index, widget)
        self._relayout()
        self._notify()

    def _add_after(self, item: tk.Widget) -> None:
        self._insert(self._create_condition(), item)

    def _move(self, row: tk.Widget, offset: int) -> None:
        index = self._items.index(row)
        target = index + offset
        if 0 <= target < len(self._items):
            self._items[index], self._items[target] = (
                self._items[target],
                self._items[index],
            )
            self._relayout()
            self._notify()

    def _relayout(self) -> None:
        """Grid children with the group's operator between each pair."""
        wanted = max(len(self._items) - 1, 0)
        while len(self._separators) < wanted:
            separator = ttk.Combobox(
                self.body,
                textvariable=self.operator,
                values=(AND, OR),
                state="readonly" if self._enabled else "disabled",
                width=5,
            )
            separator.bind("<<ComboboxSelected>>", lambda _event: self._notify())
            self._separators.append(separator)
        while len(self._separators) > wanted:
            self._separators.pop().destroy()

        row = 0
        for index, item in enumerate(self._items):
            if index:
                self._separators[index - 1].grid(
                    row=row, column=0, sticky="w", pady=(0, 4)
                )
                row += 1
            item.grid(row=row, column=0, sticky="ew", pady=(0, 4))
            row += 1
