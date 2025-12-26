# This Python file uses the following encoding: utf-8
# min python version 3.12
import sys
import re
import os
import tempfile
import subprocess

from dataclasses import dataclass

from pathlib import Path

from PySide6.QtCore import QAbstractListModel
from PySide6.QtCore import QObject
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot
from PySide6.QtCore import Qt
from PySide6.QtCore import QModelIndex
from PySide6.QtCore import QByteArray
from PySide6.QtCore import Property

from PySide6.QtGui import QGuiApplication

from PySide6.QtQml import QQmlApplicationEngine


@dataclass
class HostEntry:
    enabled: bool
    ip: str
    hosts: str


@dataclass
class HostsFileState:
    pre_lines: list[str]
    post_lines: list[str]


class HostsFileManager:
    BEGIN_MARKER: str = "# === BEGIN MANAGED BY LHM ==="
    END_MARKER: str = "# === END MANAGED BY LHM ==="

    _IP_RE: re.Pattern[str] = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3}|[0-9a-fA-F:]+)$")

    def __init__(self, path: Path | str = "/etc/hosts"):
        self._path: Path = Path(path)

    def path(self) -> Path:
        return self._path

    def template(self) -> Path:
        return self._path.parent / f".{self._path.name}_XXXXXX"

    def load_managed_block(self) -> tuple[list[HostEntry], HostsFileState]:
        """
        Читає /etc/hosts, повертає:
          - entries з керованого блоку
          - state (все до блоку і все після блоку), щоб точно відновити при записі
        Якщо маркерів немає — entries=[], state.pre_lines=весь файл, state.post_lines=[]
        """
        text: str = self._path.read_text(encoding="utf-8", errors="replace")
        lines: list[str] = text.splitlines(keepends=True)

        begin_idx: int = -1
        end_idx: int = -1

        for i, ln in enumerate(lines):
            if ln.rstrip("\n") == self.BEGIN_MARKER:
                begin_idx = i
                break

        if begin_idx != -1:
            for j in range(begin_idx + 1, len(lines)):
                if lines[j].rstrip("\n") == self.END_MARKER:
                    end_idx = j
                    break

        if begin_idx == -1 or end_idx == -1 or end_idx < begin_idx:
            return [], HostsFileState(pre_lines=lines, post_lines=[])

        pre_lines: list[str] = lines[:begin_idx]
        managed_lines: list[str] = lines[begin_idx + 1 : end_idx]
        post_lines: list[str] = lines[end_idx + 1 :]

        entries: list[HostEntry] = []
        for ln in managed_lines:
            e: HostEntry | None = self._parse_entry_line(ln)
            if e is not None:
                entries.append(e)

        return entries, HostsFileState(pre_lines=pre_lines, post_lines=post_lines)

    def build_content(self, state: HostsFileState,
                            entries: list[HostEntry]) -> str:
        pre: list[str] = list(state.pre_lines)
        post: list[str] = list(state.post_lines)

        if pre and not pre[-1].endswith("\n"):
            pre[-1] = pre[-1] + "\n"
        if pre and pre[-1].strip() != "":
            pre.append("\n")

        block: list[str] = self._render_managed_block(entries)
        return "".join(pre + block + post)

    def _parse_entry_line(self, raw: str) -> HostEntry | None:
        """
        Підтримує:
          - '1.2.3.4 host1 host2'
          - '#1.2.3.4 host1 host2' або '# 1.2.3.4 host1 host2' (disabled)
        Порожні/коментарні/некоректні -> None
        """
        s: str = raw.strip()
        if not s:
            return None

        enabled: bool = True
        if s.startswith("#"):
            enabled = False
            s = s[1:].lstrip()
            if not s:
                return None

        s = self._strip_inline_comment(s).strip()
        if not s:
            return None

        parts: list[str] = s.split()
        if len(parts) < 2:
            return None

        ip: str = parts[0]
        if self._IP_RE.match(ip) is None:
            return None

        hosts: str = " ".join(parts[1:])
        return HostEntry(enabled=enabled, ip=ip, hosts=hosts)

    def _strip_inline_comment(self, s: str) -> str:
        if "#" not in s:
            return s
        left, _hash, _right = s.partition("#")
        return left.rstrip()

    def _render_managed_block(self, entries: list[HostEntry]) -> list[str]:
        out: list[str] = []
        out.append(self.BEGIN_MARKER + "\n")

        for e in entries:
            line: str = f"{e.ip}\t{e.hosts}".rstrip()
            if not e.enabled:
                line = "#" + line
            out.append(line + "\n")

        out.append(self.END_MARKER + "\n")
        return out

    def atomic_write(self, content: str) -> None:
        dir_path: str = str(self._path.parent)

        st = None
        try:
            st = os.stat(self._path)
        except FileNotFoundError:
            st = None

        fd, tmp_path = tempfile.mkstemp(prefix=".hosts_", dir=dir_path, text=True)
        try:
            if st is not None:
                try:
                    os.fchown(fd, st.st_uid, st.st_gid)
                except PermissionError:
                    pass
                os.fchmod(fd, st.st_mode & 0o777)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(self._path))
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass


class HostsModel(QAbstractListModel):
    changed = Signal()

    EnabledRole = Qt.UserRole + 1
    IpRole = Qt.UserRole + 2
    HostsRole = Qt.UserRole + 3

    def __init__(self, entries: list[HostEntry] | None = None,
                       parent: QObject | None = None):
        super().__init__(parent)
        self._entries = list(entries or [])
        self._ensure_trailing_empty()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index: QModelIndex,
                   role: int = Qt.DisplayRole) -> object | None:
        if not index.isValid():
            return None
        e = self._entries[index.row()]
        if role == self.EnabledRole:
            return e.enabled
        if role == self.IpRole:
            return e.ip
        if role == self.HostsRole:
            return e.hosts
        return None

    def setData(self, index: QModelIndex, value: object,
                      role: int =Qt.EditRole) -> bool:
        if not index.isValid():
            return False
        row = index.row()
        e = self._entries[row]
        changed = False

        if role == self.EnabledRole:
            v = bool(value)
            if e.enabled != v:
                e.enabled = v
                changed = True
        elif role == self.IpRole:
            v = str(value)
            if e.ip != v:
                e.ip = v
                changed = True
        elif role == self.HostsRole:
            v = str(value)
            if e.hosts != v:
                e.hosts = v
                changed = True
        else:
            return False

        if changed:
            self.dataChanged.emit(index, index, [role])
            if row == len(self._entries) - 1 and not self._is_empty_entry(e):
                self._ensure_trailing_empty()
            self._prune_empty_rows()
            self.changed.emit()
        return changed

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.EnabledRole: QByteArray(b"enabled"),
            self.IpRole: QByteArray(b"ip"),
            self.HostsRole: QByteArray(b"hosts"),
        }

    @Slot(int, bool)
    def setEnabled(self, row: int, enabled: bool):
        if not self._row_ok(row):
            return
        self.setData(self.index(row, 0), enabled, self.EnabledRole)

    @Slot(int, str)
    def setIp(self, row: int, ip: str):
        if not self._row_ok(row):
             return
        self.setData(self.index(row, 0), ip, self.IpRole)

    @Slot(int, str)
    def setHosts(self, row: int, hosts: str):
        if not self._row_ok(row):
            return
        self.setData(self.index(row, 0), hosts, self.HostsRole)

    def _row_ok(self, row: int) -> bool:
        return 0 <= row < len(self._entries)

    def entries_snapshot(self) -> list[HostEntry]:
        return [
            HostEntry(e.enabled, e.ip, e.hosts)
            for e in self._entries
            if not self._is_empty_entry(e)
        ]

    def set_entries(self, entries: list[HostEntry]):
        self.beginResetModel()
        self._entries = list(entries)
        self._ensure_trailing_empty()
        self.endResetModel()
        self.changed.emit()

    def _is_empty_entry(self, e: HostEntry) -> bool:
        return not e.ip.strip() and not e.hosts.strip()

    def _ensure_trailing_empty(self):
        if not self._entries or not self._is_empty_entry(self._entries[-1]):
            self.beginInsertRows(QModelIndex(), len(self._entries), len(self._entries))
            self._entries.append(HostEntry(True, "", ""))
            self.endInsertRows()

    def _prune_empty_rows(self) -> None:
        i = 0
        while i < len(self._entries) - 1:
            if self._is_empty_entry(self._entries[i]):
                self.beginRemoveRows(QModelIndex(), i, i)
                self._entries.pop(i)
                self.endRemoveRows()
                continue
            i += 1


class AppEngine(QObject):
    dirtyChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(self, model: HostsModel):
        super().__init__()
        self._model = model
        self._hosts = HostsFileManager("/etc/hosts")
        self._dirty = False
        entries, state = self._hosts.load_managed_block()
        self._state = state
        self._model.set_entries(entries)
        self._snapshot = model.entries_snapshot()

        self._model.changed.connect(self._on_model_changed)

    @Slot()
    def _on_model_changed(self):
        self._set_dirty(True)

    def _set_dirty(self, v: bool):
        if self._dirty == v:
            return
        self._dirty = v
        self.dirtyChanged.emit()

    def getDirty(self) -> bool:
        return self._dirty

    dirty = Property(bool, getDirty, notify=dirtyChanged)

    @Slot()
    def apply(self):
        entries = self._model.entries_snapshot()
        content = self._hosts.build_content(self._state, entries)

        try:
            self._hosts.atomic_write(content)
        except PermissionError:
            try:
                p = subprocess.run(
                    [
                        "/usr/bin/pkexec",
                        "/bin/sh",
                        "-c",
                        fr'tmp="$(mktemp { str(self._hosts.template()) })" && '
                        r'cat > "$tmp" && '
                        r'chown root:root "$tmp" && chmod 0644 "$tmp" && '
                        fr'mv -f "$tmp" { str(self._hosts.path()) }'
                    ],
                    input=content,
                    text=True,
                    capture_output=True,
                )
            except FileNotFoundError:
                self.errorOccurred.emit(
                    "Не знайдено pkexec. Встанови пакет polkit (pkexec) "
                    "або запускай через sudo/pkexec.")
                return

            if p.returncode != 0:
                err = (p.stderr or "").strip()
                self.errorOccurred.emit(
                    "Не вдалося застосувати зміни через pkexec."
                    + (f" Деталі: {err}" if err else ""))
                return

        self._snapshot = self._model.entries_snapshot()
        self._set_dirty(False)

    @Slot()
    def revert(self):
        self._model.set_entries(self._snapshot)
        self._set_dirty(False)


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)

    model = HostsModel()
    appEngine = AppEngine(model)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("hostsModel", model)
    engine.rootContext().setContextProperty("appEngine", appEngine)

    qml_file = Path(__file__).resolve().parent / "main.qml"
    engine.load(qml_file)

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())
