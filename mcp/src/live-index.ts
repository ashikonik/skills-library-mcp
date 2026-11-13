/**
 * A live view of the index file.
 *
 * The index is ~5 MB and is read once at startup. That was fine while
 * the library changed only between builds — but a long-running server
 * outlives the build that preceded it, and a server serving a stale
 * index answers *confidently and wrongly*: `get_agent` says "not
 * found" for an agent that is on disk, and `search_library` cannot
 * find what the caller just added.
 *
 * That failure is silent in the worst way. Nothing errors; the server
 * simply reports a library that is smaller than the library.
 *
 * So the index is watched. The file's mtime and size are checked
 * before each tool call; when either changes, the file is re-read and
 * the search index is rebuilt. The cost is one `stat` per call.
 *
 * The staleness check is on the *file*, not on any in-memory state,
 * because the file is the shared artifact: the Python server reads
 * the same path, and the two must never disagree about what the
 * library contains.
 */
import { statSync } from 'node:fs';
import type { LibraryIndex } from './types.js';
import { loadIndex, indexPath } from './index-loader.js';

/** What the watcher remembers about the file it last read. */
interface Fingerprint {
  mtimeMs: number;
  size: number;
}

/**
 * A live index, and the search engine built over it.
 *
 * The search engine is rebuilt alongside the index because it holds
 * BM25 statistics derived from the corpus: a search index built over
 * 1146 entries cannot correctly rank a corpus of 1147.
 */
export class LiveIndex {
  private index: LibraryIndex;
  private fingerprint: Fingerprint;
  private readonly path: string;

  constructor(path?: string, index?: LibraryIndex) {
    this.path = path ?? indexPath();
    this.index = index ?? loadIndex(this.path);
    this.fingerprint = this.readFingerprint();
  }

  /** The current index, reloading it first if the file has changed. */
  current(): LibraryIndex {
    const now = this.readFingerprint();
    if (!now) return this.index;
    if (
      now.mtimeMs !== this.fingerprint.mtimeMs ||
      now.size !== this.fingerprint.size
    ) {
      const reloaded = loadIndex(this.path);
      this.index = reloaded;
      this.fingerprint = now;
    }
    return this.index;
  }

  /**
   * Whether the file changed since it was last read.
   *
   * A file that cannot be stat'd is reported as unchanged: the index
   * already in hand is better than an error, and the file was there a
   * moment ago.
   */
  private readFingerprint(): Fingerprint {
    const stat = statSync(this.path, { throwIfNoEntry: false });
    if (!stat) return { mtimeMs: 0, size: 0 };
    return { mtimeMs: stat.mtimeMs, size: stat.size };
  }
}
