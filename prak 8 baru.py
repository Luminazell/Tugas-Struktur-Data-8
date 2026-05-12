"""
Note-Taking App — Struktur Data Profesional
============================================
Fitur:
  1. Multiple tags per note  (multi-linked hash map by tag)
  2. Chronological & alphabetical views  (doubly linked list, sorted)
  3. Sync status tracking  (circular buffer untuk recent changes)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ─────────────────────────────────────────────
# 1.  ENUMS & CONSTANTS
# ─────────────────────────────────────────────

class SyncStatus(Enum):
    PENDING   = auto()   # belum di-sync
    SYNCING   = auto()   # sedang di-sync
    SYNCED    = auto()   # sudah di-sync
    CONFLICT  = auto()   # konflik dengan server
    FAILED    = auto()   # sync gagal


BUFFER_CAPACITY = 50   # maks recent changes yang disimpan


# ─────────────────────────────────────────────
# 2.  NOTE NODE  (simpul doubly linked list)
# ─────────────────────────────────────────────

@dataclass
class NoteNode:
    """Satu catatan sekaligus menjadi simpul dalam dua doubly linked list."""

    note_id:    str            = field(default_factory=lambda: str(uuid.uuid4()))
    title:      str            = ""
    content:    str            = ""
    tags:       set[str]       = field(default_factory=set)
    created_at: float          = field(default_factory=time.time)
    updated_at: float          = field(default_factory=time.time)
    sync_status: SyncStatus    = SyncStatus.PENDING

    # pointer untuk Chronological DLL (urut waktu)
    chron_prev: Optional[NoteNode] = field(default=None, repr=False)
    chron_next: Optional[NoteNode] = field(default=None, repr=False)

    # pointer untuk Alphabetical DLL (urut judul)
    alpha_prev: Optional[NoteNode] = field(default=None, repr=False)
    alpha_next: Optional[NoteNode] = field(default=None, repr=False)

    def touch(self) -> None:
        """Perbarui timestamp saat note diedit."""
        self.updated_at = time.time()

    def __hash__(self) -> int:
        return hash(self.note_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NoteNode):
            return NotImplemented
        return self.note_id == other.note_id

    def __repr__(self) -> str:
        return (
            f"NoteNode(id={self.note_id[:8]}…, "
            f"title={self.title!r}, "
            f"tags={self.tags}, "
            f"sync={self.sync_status.name})"
        )


# ─────────────────────────────────────────────
# 3.  DOUBLY LINKED LIST  (generic, sorted)
# ─────────────────────────────────────────────

class SortedDoublyLinkedList:
    """
    DLL yang selalu terurut berdasarkan key_fn.
    Mendukung traversal maju (head→tail) & mundur (tail→head).
    """

    def __init__(self, key_fn, prev_attr: str, next_attr: str):
        """
        key_fn   : fungsi pengambil kunci sorting dari NoteNode
        prev_attr: nama atribut pointer 'prev' di NoteNode
        next_attr: nama atribut pointer 'next' di NoteNode
        """
        self._key     = key_fn
        self._prev    = prev_attr
        self._next    = next_attr
        self.head: Optional[NoteNode] = None
        self.tail: Optional[NoteNode] = None
        self.size: int = 0

    # ── helpers ────────────────────────────────

    def _set_prev(self, node: NoteNode, value: Optional[NoteNode]) -> None:
        setattr(node, self._prev, value)

    def _set_next(self, node: NoteNode, value: Optional[NoteNode]) -> None:
        setattr(node, self._next, value)

    def _get_prev(self, node: NoteNode) -> Optional[NoteNode]:
        return getattr(node, self._prev)

    def _get_next(self, node: NoteNode) -> Optional[NoteNode]:
        return getattr(node, self._next)

    # ── operasi utama ──────────────────────────

    def insert(self, node: NoteNode) -> None:
        """Sisipkan node pada posisi yang tepat (O(n) worst case)."""
        self._set_prev(node, None)
        self._set_next(node, None)

        if self.head is None:
            self.head = self.tail = node
            self.size += 1
            return

        # cari posisi yang benar
        cur = self.head
        while cur and self._key(cur) <= self._key(node):
            cur = self._get_next(cur)

        if cur is None:
            # node masuk paling belakang
            self._set_prev(node, self.tail)
            self._set_next(self.tail, node)  # type: ignore[arg-type]
            self.tail = node
        else:
            pred = self._get_prev(cur)
            self._set_next(node, cur)
            self._set_prev(node, pred)
            if pred:
                self._set_next(pred, node)
            else:
                self.head = node
            self._set_prev(cur, node)

        self.size += 1

    def remove(self, node: NoteNode) -> None:
        """Hapus node dari DLL (O(1) karena pointer langsung)."""
        prev_node = self._get_prev(node)
        next_node = self._get_next(node)

        if prev_node:
            self._set_next(prev_node, next_node)
        else:
            self.head = next_node

        if next_node:
            self._set_prev(next_node, prev_node)
        else:
            self.tail = prev_node

        self._set_prev(node, None)
        self._set_next(node, None)
        self.size -= 1

    def reinsert(self, node: NoteNode) -> None:
        """Hapus lalu sisipkan ulang (gunakan setelah note diedit)."""
        self.remove(node)
        self.insert(node)

    # ── traversal ──────────────────────────────

    def forward(self) -> list[NoteNode]:
        """Kembalikan list node dari head ke tail."""
        result, cur = [], self.head
        while cur:
            result.append(cur)
            cur = self._get_next(cur)
        return result

    def backward(self) -> list[NoteNode]:
        """Kembalikan list node dari tail ke head."""
        result, cur = [], self.tail
        while cur:
            result.append(cur)
            cur = self._get_prev(cur)
        return result


# ─────────────────────────────────────────────
# 4.  CIRCULAR BUFFER  (sync recent changes)
# ─────────────────────────────────────────────

@dataclass
class SyncEvent:
    note_id:    str
    status:     SyncStatus
    timestamp:  float = field(default_factory=time.time)
    detail:     str   = ""

    def __repr__(self) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        return f"[{ts}] {self.note_id[:8]}… → {self.status.name}: {self.detail}"


class CircularBuffer:
    """
    Buffer melingkar berkapasitas tetap untuk melacak perubahan sync terbaru.
    Saat penuh, entri terlama otomatis ditimpa.
    """

    def __init__(self, capacity: int = BUFFER_CAPACITY):
        self.capacity   = capacity
        self._buffer: list[Optional[SyncEvent]] = [None] * capacity
        self._head      = 0   # posisi tulis berikutnya
        self._count     = 0   # jumlah elemen aktif

    def push(self, event: SyncEvent) -> None:
        """Tambahkan event baru; timpa terlama jika penuh."""
        self._buffer[self._head] = event
        self._head  = (self._head + 1) % self.capacity
        self._count = min(self._count + 1, self.capacity)

    def latest(self, n: int = 10) -> list[SyncEvent]:
        """Kembalikan n event terbaru (terbaru di indeks 0)."""
        n = min(n, self._count)
        result = []
        idx = (self._head - 1) % self.capacity
        for _ in range(n):
            if self._buffer[idx] is not None:
                result.append(self._buffer[idx])
            idx = (idx - 1) % self.capacity
        return result   # type: ignore[return-value]

    def __len__(self) -> int:
        return self._count

    def __repr__(self) -> str:
        return f"CircularBuffer(capacity={self.capacity}, count={self._count})"


# ─────────────────────────────────────────────
# 5.  TAG INDEX  (multi-linked by tag)
# ─────────────────────────────────────────────

class TagIndex:
    """
    Hash map  tag → set of NoteNode
    Mendukung O(1) lookup notes per tag.
    """

    def __init__(self):
        self._index: dict[str, set[NoteNode]] = {}

    def add(self, tag: str, node: NoteNode) -> None:
        self._index.setdefault(tag, set()).add(node)

    def remove(self, tag: str, node: NoteNode) -> None:
        if tag in self._index:
            self._index[tag].discard(node)
            if not self._index[tag]:
                del self._index[tag]

    def get_notes(self, tag: str) -> set[NoteNode]:
        return self._index.get(tag, set())

    def all_tags(self) -> list[str]:
        return sorted(self._index.keys())


# ─────────────────────────────────────────────
# 6.  NOTE MANAGER  (fasad utama)
# ─────────────────────────────────────────────

class NoteManager:
    """
    Antarmuka tunggal untuk semua operasi pada aplikasi note-taking.

    Struktur data yang digunakan:
      • dict[str, NoteNode]         — pencarian O(1) by ID
      • TagIndex                    — multi-tag lookup O(1)
      • SortedDoublyLinkedList (×2) — chronological & alphabetical views
      • CircularBuffer              — 50 recent sync events
    """

    def __init__(self, buffer_capacity: int = BUFFER_CAPACITY):
        self._notes: dict[str, NoteNode] = {}
        self._tags  = TagIndex()
        self._chron = SortedDoublyLinkedList(
            key_fn    = lambda n: n.created_at,
            prev_attr = "chron_prev",
            next_attr = "chron_next",
        )
        self._alpha = SortedDoublyLinkedList(
            key_fn    = lambda n: n.title.lower(),
            prev_attr = "alpha_prev",
            next_attr = "alpha_next",
        )
        self._sync_log = CircularBuffer(buffer_capacity)

    # ── CRUD ───────────────────────────────────

    def create_note(self, title: str, content: str = "", tags: set[str] | None = None) -> NoteNode:
        node = NoteNode(title=title, content=content, tags=tags or set())
        self._notes[node.note_id] = node
        for tag in node.tags:
            self._tags.add(tag, node)
        self._chron.insert(node)
        self._alpha.insert(node)
        self._record_sync(node, SyncStatus.PENDING, "Note created")
        return node

    def get_note(self, note_id: str) -> Optional[NoteNode]:
        return self._notes.get(note_id)

    def update_note(
        self,
        note_id: str,
        title:   Optional[str] = None,
        content: Optional[str] = None,
        add_tags:    set[str]  | None = None,
        remove_tags: set[str]  | None = None,
    ) -> Optional[NoteNode]:
        node = self._notes.get(note_id)
        if node is None:
            return None

        if title is not None:
            node.title = title
            self._alpha.reinsert(node)    # urutan abjad mungkin berubah

        if content is not None:
            node.content = content

        for tag in (remove_tags or set()):
            node.tags.discard(tag)
            self._tags.remove(tag, node)

        for tag in (add_tags or set()):
            node.tags.add(tag)
            self._tags.add(tag, node)

        node.touch()
        self._record_sync(node, SyncStatus.PENDING, "Note updated")
        return node

    def delete_note(self, note_id: str) -> bool:
        node = self._notes.pop(note_id, None)
        if node is None:
            return False
        for tag in node.tags:
            self._tags.remove(tag, node)
        self._chron.remove(node)
        self._alpha.remove(node)
        self._record_sync(node, SyncStatus.PENDING, "Note deleted")
        return True

    # ── VIEWS ──────────────────────────────────

    def view_chronological(self, reverse: bool = False) -> list[NoteNode]:
        """Semua note urut waktu (terlama duluan; reverse=True → terbaru duluan)."""
        return self._chron.backward() if reverse else self._chron.forward()

    def view_alphabetical(self, reverse: bool = False) -> list[NoteNode]:
        """Semua note urut abjad judul."""
        return self._alpha.backward() if reverse else self._alpha.forward()

    def view_by_tag(self, tag: str) -> set[NoteNode]:
        """Semua note yang memiliki tag tertentu."""
        return self._tags.get_notes(tag)

    # ── SYNC ───────────────────────────────────

    def mark_synced(self, note_id: str) -> None:
        node = self._notes.get(note_id)
        if node:
            node.sync_status = SyncStatus.SYNCED
            self._record_sync(node, SyncStatus.SYNCED, "Sync successful")

    def mark_failed(self, note_id: str, reason: str = "") -> None:
        node = self._notes.get(note_id)
        if node:
            node.sync_status = SyncStatus.FAILED
            self._record_sync(node, SyncStatus.FAILED, reason or "Sync failed")

    def pending_sync(self) -> list[NoteNode]:
        """Semua note yang belum/gagal di-sync."""
        return [n for n in self._notes.values() if n.sync_status in (SyncStatus.PENDING, SyncStatus.FAILED)]

    def recent_sync_events(self, n: int = 10) -> list[SyncEvent]:
        return self._sync_log.latest(n)

    def _record_sync(self, node: NoteNode, status: SyncStatus, detail: str) -> None:
        self._sync_log.push(SyncEvent(note_id=node.note_id, status=status, detail=detail))

    # ── INFO ───────────────────────────────────

    def stats(self) -> dict:
        return {
            "total_notes"    : len(self._notes),
            "total_tags"     : len(self._tags.all_tags()),
            "pending_sync"   : len(self.pending_sync()),
            "sync_log_size"  : len(self._sync_log),
            "chron_dll_size" : self._chron.size,
            "alpha_dll_size" : self._alpha.size,
        }

    def __repr__(self) -> str:
        return f"NoteManager(notes={len(self._notes)}, tags={self._tags.all_tags()})"


# ─────────────────────────────────────────────
# 7.  DEMO / SELF-TEST
# ─────────────────────────────────────────────

def demo() -> None:
    print("=" * 60)
    print("  NOTE-TAKING APP — Demo Struktur Data")
    print("=" * 60)

    mgr = NoteManager()

    # Buat beberapa note
    n1 = mgr.create_note("Belajar Python",   "List, dict, set...",      tags={"python", "belajar"})
    n2 = mgr.create_note("Algoritma Sorting","Bubble, merge, quick...", tags={"cs", "belajar"})
    n3 = mgr.create_note("Agama Islam",      "Rukun iman & islam...",   tags={"agama"})
    n4 = mgr.create_note("Circular Buffer",  "Fixed-size ring buffer.", tags={"cs", "python"})

    time.sleep(0.01)   # pastikan timestamp berbeda
    n5 = mgr.create_note("Zen of Python",    "Beautiful is better...",  tags={"python"})

    # Update note
    mgr.update_note(n1.note_id, title="Belajar Python 3", add_tags={"oop"})

    # ── View chronological ──
    print("\n📅  Chronological (terlama → terbaru):")
    for i, n in enumerate(mgr.view_chronological(), 1):
        print(f"  {i}. {n.title}")

    print("\n📅  Chronological (terbaru → terlama):")
    for i, n in enumerate(mgr.view_chronological(reverse=True), 1):
        print(f"  {i}. {n.title}")

    # ── View alphabetical ──
    print("\n🔤  Alphabetical:")
    for i, n in enumerate(mgr.view_alphabetical(), 1):
        print(f"  {i}. {n.title}")

    # ── View by tag ──
    print("\n🏷️   Notes bertag 'python':")
    for n in mgr.view_by_tag("python"):
        print(f"  • {n.title}  (tags: {n.tags})")

    print("\n🏷️   Notes bertag 'belajar':")
    for n in mgr.view_by_tag("belajar"):
        print(f"  • {n.title}")

    # ── Sync ──
    mgr.mark_synced(n2.note_id)
    mgr.mark_failed(n3.note_id, "Network timeout")

    print("\n🔄  Recent sync events:")
    for ev in mgr.recent_sync_events(6):
        print(f"  {ev}")

    print(f"\n⏳  Pending sync: {[n.title for n in mgr.pending_sync()]}")

    # ── Hapus ──
    mgr.delete_note(n4.note_id)
    print(f"\n🗑️   Setelah delete 'Circular Buffer' → total: {len(mgr._notes)} notes")

    # ── Stats ──
    print("\n📊  Stats:")
    for k, v in mgr.stats().items():
        print(f"  {k:<20}: {v}")

    print("\n" + "=" * 60)
    print("  Semua struktur data bekerja dengan benar ✓")
    print("=" * 60)


if __name__ == "__main__":
    demo()