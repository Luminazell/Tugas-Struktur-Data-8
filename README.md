# 📝 Note-Taking App — Struktur Data

Implementasi profesional struktur data untuk aplikasi note-taking menggunakan Python murni (tanpa library eksternal).

---

## ✨ Fitur Utama

| Fitur | Struktur Data | Kompleksitas |
|---|---|---|
| Multiple tags per note | `TagIndex` → `dict[str, set[NoteNode]]` | O(1) lookup |
| Chronological view | `SortedDoublyLinkedList` (key: `created_at`) | O(n) traversal |
| Alphabetical view | `SortedDoublyLinkedList` (key: `title.lower()`) | O(n) traversal |
| Sync status tracking | `CircularBuffer` (kapasitas 50 event) | O(1) push & read |
| Lookup by ID | `dict[str, NoteNode]` | O(1) |

---

## 🏗️ Arsitektur

```
NoteManager (fasad utama)
├── dict[note_id → NoteNode]       ← pencarian cepat by ID
├── TagIndex                        ← multi-tag hash map
│   └── dict[tag → set[NoteNode]]
├── SortedDoublyLinkedList (chron)  ← urut waktu (created_at)
│   └── head ↔ node ↔ node ↔ tail
├── SortedDoublyLinkedList (alpha)  ← urut abjad (title)
│   └── head ↔ node ↔ node ↔ tail
└── CircularBuffer                  ← 50 recent sync events
    └── [ring buffer fixed-size]
```

### NoteNode — Simpul Ganda

Setiap `NoteNode` menyimpan **dua pasang pointer** sekaligus, sehingga satu objek dapat tinggal di dua DLL berbeda tanpa duplikasi data:

```
NoteNode
├── chron_prev / chron_next   → posisi di DLL kronologis
└── alpha_prev / alpha_next   → posisi di DLL alfabetis
```

---

## 📦 Komponen

### `NoteNode`
Dataclass yang merepresentasikan satu catatan. Berperan sebagai simpul di dua DLL sekaligus.

```python
node = NoteNode(
    title   = "Belajar Python",
    content = "List, dict, set...",
    tags    = {"python", "belajar"},
)
```

**Atribut penting:**

| Atribut | Tipe | Keterangan |
|---|---|---|
| `note_id` | `str` (UUID4) | ID unik otomatis |
| `title` | `str` | Judul catatan |
| `content` | `str` | Isi catatan |
| `tags` | `set[str]` | Kumpulan tag |
| `created_at` | `float` | Unix timestamp pembuatan |
| `updated_at` | `float` | Unix timestamp terakhir edit |
| `sync_status` | `SyncStatus` | Status sinkronisasi |

---

### `SortedDoublyLinkedList`
DLL generik yang selalu terurut berdasarkan `key_fn`. Mendukung:
- Traversal maju (`head → tail`) dan mundur (`tail → head`)
- Insert terurut O(n)
- Remove O(1) (pointer langsung)
- Reinsert O(n) setelah edit

```python
dll = SortedDoublyLinkedList(
    key_fn    = lambda n: n.created_at,
    prev_attr = "chron_prev",
    next_attr = "chron_next",
)
dll.insert(node)
dll.forward()    # [node1, node2, ...]
dll.backward()   # [nodeN, ..., node1]
```

---

### `TagIndex`
Hash map `tag → set[NoteNode]` untuk pencarian multi-tag O(1).

```python
tag_index = TagIndex()
tag_index.add("python", node)
tag_index.get_notes("python")   # → set of NoteNode
tag_index.all_tags()            # → ['belajar', 'cs', 'python']
```

---

### `CircularBuffer`
Buffer melingkar berkapasitas tetap untuk melacak perubahan sync terbaru. Saat penuh, entri terlama **otomatis ditimpa**.

```python
buf = CircularBuffer(capacity=50)
buf.push(SyncEvent(note_id="abc", status=SyncStatus.SYNCED))
buf.latest(n=10)   # → 10 event terbaru
```

**Cara kerja ring buffer:**
```
[ E4 | E5 | E1 | E2 | E3 ]
          ↑
         head (posisi tulis berikutnya)
```

---

### `SyncStatus` (Enum)

| Status | Keterangan |
|---|---|
| `PENDING` | Belum di-sync |
| `SYNCING` | Sedang di-sync |
| `SYNCED` | Berhasil di-sync |
| `CONFLICT` | Konflik dengan server |
| `FAILED` | Sync gagal |

---

## 🚀 Cara Penggunaan

```python
from note_taking_app import NoteManager

mgr = NoteManager()

# Buat note
n1 = mgr.create_note("Judul", "Konten...", tags={"python", "cs"})

# Update note
mgr.update_note(n1.note_id, title="Judul Baru", add_tags={"oop"})

# View semua note
mgr.view_chronological()           # urut waktu (lama → baru)
mgr.view_chronological(reverse=True)   # baru → lama
mgr.view_alphabetical()            # urut abjad A → Z

# Filter by tag
mgr.view_by_tag("python")          # → set[NoteNode]

# Sync
mgr.mark_synced(n1.note_id)
mgr.mark_failed(n1.note_id, reason="Network timeout")
mgr.pending_sync()                 # semua yang belum/gagal sync
mgr.recent_sync_events(n=10)       # 10 event terakhir

# Hapus
mgr.delete_note(n1.note_id)

# Statistik
mgr.stats()
```

---

## ▶️ Menjalankan Demo

```bash
python note_taking_app.py
```

Output yang diharapkan:

```
============================================================
  NOTE-TAKING APP — Demo Struktur Data
============================================================

📅  Chronological (terlama → terbaru):
  1. Belajar Python 3
  2. Algoritma Sorting
  ...

🔤  Alphabetical:
  1. Agama Islam
  2. Algoritma Sorting
  ...

📊  Stats:
  total_notes         : 4
  total_tags          : 5
  ...
============================================================
  Semua struktur data bekerja dengan benar ✓
============================================================
```

---

## 📁 Struktur File

```
.
├── note_taking_app.py   ← implementasi lengkap + demo
└── README.md            ← dokumentasi ini
```

---

## 🔧 Persyaratan

- Python **3.10+** (menggunakan `match`-style type hints & `dataclass`)
- Tidak memerlukan library eksternal

---

## 📐 Keputusan Desain

**Mengapa dua DLL terpisah bukan satu?**
Chronological dan alphabetical adalah urutan yang **saling independen**. Satu DLL hanya bisa terurut menurut satu kriteria. Dengan dua DLL dan dua pasang pointer di setiap node, switching view O(1) tanpa re-sort.

**Mengapa CircularBuffer bukan `deque`?**
`deque(maxlen=N)` bisa dipakai, tapi CircularBuffer custom memberikan kontrol eksplisit atas indeks read/write dan mengilustrasikan konsep ring buffer secara langsung — penting untuk tujuan pembelajaran.

**Mengapa `set[NoteNode]` di TagIndex?**
Lookup keberadaan tag O(1) dan menghindari duplikasi node dalam satu tag secara otomatis.
