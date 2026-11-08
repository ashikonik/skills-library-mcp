/**
 * The protocol revision, and the behaviour that depends on it.
 *
 * This is the TypeScript half of the pair `mcp/src/protocol.ts` and
 * `mcp/python/protocol.py`. The three files together -- the two
 * protocol modules and this one -- own every decision that differs
 * between the revisions.
 *
 * The SDK does not know about `2026-07-28`. Its own list of supported
 * versions stops at `2025-11-25`, and a client asking for the newer
 * revision would be silently answered with the older one -- a
 * downgrade the client never asked for and cannot detect. So the
 * `initialize` handler is replaced, and the replacement negotiates
 * the revision itself.
 *
 * The older revision's output is unchanged. A client that never asked
 * for the new revision sees exactly the fields it saw before, which
 * is what keeps the agreement gate's byte-for-byte comparison honest.
 */
import {
  InitializeRequestSchema,
  ListToolsRequestSchema,
  CallToolRequestSchema,
  McpError,
  ErrorCode,
} from '@modelcontextprotocol/sdk/types.js';
import type { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
  SUPPORTED_PROTOCOL_VERSIONS,
  DEFAULT_PROTOCOL_VERSION,
  CURRENT_PROTOCOL_VERSION,
  negotiate,
  isCurrent,
  resultType,
  cacheFields,
} from './protocol.js';
import {
  SKILLS_EXTENSION_ID,
  SKILLS_TTL_MS,
  SkillError,
  listSkills,
  listResources,
  findByUri,
  findSkillMd,
  readSkillFile,
  readSkillDirectory,
  skillEntry,
} from './skills-extension.js';
import type { LibraryIndex } from './types.js';

export {
  SUPPORTED_PROTOCOL_VERSIONS,
  DEFAULT_PROTOCOL_VERSION,
  CURRENT_PROTOCOL_VERSION,
  negotiate,
  isCurrent,
  resultType,
  cacheFields,
};

/** The Skills extension (SEP-2640). */
export const SKILLS_EXTENSION = 'io.modelcontextprotocol/skills';

/**
 * How long a client may reuse the tool list, under the revision that
 * asks for a TTL. The tool list changes when the library changes --
 * a new skill does not add a tool, but a new harness does -- so the
 * TTL is short. It is a cache, not a snapshot.
 */
export const TOOLS_LIST_TTL_MS = 60_000;

/**
 * The state a server keeps about the revision it is talking.
 *
 * The revision is per-connection: a client negotiates it once, at
 * `initialize`, and everything after that is answered under it.
 */
export class RevisionState {
  /** The negotiated revision. */
  version: string = DEFAULT_PROTOCOL_VERSION;

  /** The revision this server falls back to. */
  get defaultVersion(): string {
    return DEFAULT_PROTOCOL_VERSION;
  }

  /** Is the client on the revision with the breaking changes? */
  get current(): boolean {
    return isCurrent(this.version);
  }
}

/**
 * The `initialize` result for a revision.
 *
 * The capabilities differ: the newer revision adds `resources` and
 * the Skills extension declaration. The older one must not have them,
 * because a client reading the old revision would try to call
 * `resources/list` against a server that answers `-32601`.
 */
export function capabilities(
  version: string,
  base: Record<string, unknown>,
): Record<string, unknown> {
  if (!isCurrent(version)) return base;
  return {
    ...base,
    resources: {},
    extensions: {
      [SKILLS_EXTENSION]: { directoryRead: true },
    },
  };
}

/**
 * The `server/discover` response.
 *
 * Mandatory under `2026-07-28`. It says what the server is, which
 * revisions it speaks, and what it can do -- so a client can find out
 * the server's shape without having to guess at it.
 *
 * It is answered under every revision, not only the new one: a client
 * that asks is asking, and refusing the question because of the
 * revision it already speaks would be answering "no" to something the
 * server could answer.
 */
export function discover(): Record<string, unknown> {
  return {
    protocolVersions: [...SUPPORTED_PROTOCOL_VERSIONS],
    capabilities: capabilities(CURRENT_PROTOCOL_VERSION, {
      tools: { listChanged: false },
    }),
    serverInfo: { name: 'skills-library', version: '1.0.0' },
    extensions: {
      [SKILLS_EXTENSION]: { directoryRead: true },
    },
  };
}

/**
 * Record the client's own capabilities and version on the server.
 *
 * The SDK's `_oninitialize` does this on its own path. The newer
 * revision does not go through `_oninitialize`, so it is done here --
 * into the same private fields, so `getClientCapabilities()` and
 * `getClientVersion()` answer the same either way.
 */
function recordClientInfo(server: Server, request: unknown): void {
  const params = (request as { params?: Record<string, unknown> } | undefined)?.params;
  const s = server as unknown as {
    _clientCapabilities?: unknown;
    _clientVersion?: unknown;
  };
  s._clientCapabilities = params?.capabilities;
  s._clientVersion = params?.clientInfo;
}

/**
 * Replace the SDK's `initialize` handler with one that negotiates the
 * revision, and register `server/discover`.
 *
 * The SDK's own handler answers `2025-11-25` to *every* client,
 * because that is the newest version it knows. Replacing it is what
 * lets a client that asks for `2026-07-28` get it.
 *
 * The SDK's `_oninitialize` also records the client's capabilities and
 * version, which the SDK uses for its own client-bound requests. The
 * replacement records them too, by calling the original handler for
 * the versions the SDK understands -- so nothing the SDK relies on is
 * lost.
 */
export function installRevisionHandlers(server: Server, state: RevisionState): void {
  // The SDK's own `initialize` handler. It is kept, not replaced: it
  // records the client's own capabilities and version -- which the SDK
  // uses for its client-bound requests -- and it knows how to build the
  // result for every revision the SDK understands.
  //
  // It is *bound* to the server. The SDK registers it as
  // `request => this._oninitialize(request)`, so calling it detached
  // would leave `this` undefined inside it -- and it writes
  // `this._clientCapabilities`, which would throw.
  const original = (server as unknown as {
    _oninitialize?: (request: unknown) => unknown;
  })._oninitialize?.bind(server);

  server.setRequestHandler(InitializeRequestSchema, async (request) => {
    const requested = request.params?.protocolVersion;
    const version = negotiate(requested);
    state.version = version;

    // For a version the SDK knows, let the SDK build the result: it
    // knows the capabilities it registered, and it records the client's
    // own capabilities and version. For the newer revision, the SDK
    // would answer with the older one, so the result is built here.
    if (version !== CURRENT_PROTOCOL_VERSION && original) {
      const result = (await original(request)) as Record<string, unknown>;
      return result;
    }

    // The newer revision. The SDK's own handler would answer with the
    // older revision's capabilities, so the result is built here -- but
    // from the SDK's own capability record, so the two cannot drift.
    //
    // `getCapabilities` is private on the SDK's `Server`; `_capabilities`
    // is the field behind it. `registerCapabilities` would mutate the
    // server permanently, which is wrong here: the revision is
    // per-connection, and a server that served two revisions in one
    // process would leak one client's revision into another's.
    //
    // The SDK's own handler also records the client's capabilities and
    // version, which it uses for client-bound requests. That does not
    // happen on this path -- `original` is not called -- so it is
    // recorded here, in the same fields the SDK uses.
    recordClientInfo(server, request);

    const base = ((server as unknown as {
      _capabilities?: Record<string, unknown>;
    })._capabilities ?? {}) as Record<string, unknown>;
    const result: Record<string, unknown> = {
      protocolVersion: version,
      capabilities: capabilities(version, base),
      serverInfo: { name: 'skills-library', version: '1.0.0' },
    };
    const instructions = (server as unknown as { _instructions?: string })._instructions;
    if (instructions) result.instructions = instructions;
    return result;
  });

  // `server/discover` is not a method the SDK knows, so it goes
  // through the fallback handler. The SDK dispatches there when no
  // handler is registered for the method.
  //
  // The fallback is also the SDK's last chance to say "no such
  // method", and it says it with `-32601`. A plain `Error` would
  // become `-32603` -- "internal error" -- which tells the client the
  // *server* broke rather than that the *method* does not exist.
  // `McpError` with `ErrorCode.MethodNotFound` is the protocol's own
  // way of saying it.
  const existingFallback = server.fallbackRequestHandler;
  server.fallbackRequestHandler = async (request, extra) => {
    if (request.method === 'server/discover') {
      return discover();
    }
    if (existingFallback) {
      return existingFallback(request, extra);
    }
    throw new McpError(ErrorCode.MethodNotFound, `Method not found: ${request.method}`);
  };
}

/**
 * The Skills extension's methods.
 *
 * None of them is a method the SDK knows, so all of them go through the
 * fallback handler. The extension is only declared -- and only
 * answered -- under the revision that has it: a client on `2025-11-25`
 * never asked for `skills/list` and would not know what to do with the
 * answer.
 *
 * `resources/list` is here too, because the `resources` capability is
 * declared: a client that reads the capability and then calls the
 * method would otherwise get `-32601` from a server that promised it.
 *
 * The results carry `resultType`, `ttlMs` and `cacheScope`, which the
 * revision that requires them also requires on these methods.
 */
export function installSkillsExtension(
  server: Server,
  state: RevisionState,
  index: LibraryIndex,
  root: string,
): void {
  const existingFallback = server.fallbackRequestHandler;

  const answer = async (method: string, params: Record<string, unknown> | undefined) => {
    switch (method) {
      case 'skills/list': {
        const page = listSkills(index, params?.cursor as string | undefined);
        return {
          skills: page.skills,
          ...(page.nextCursor ? { nextCursor: page.nextCursor } : {}),
          ...resultType(state.version),
          ...cacheFields(state.version, SKILLS_TTL_MS, 'public'),
        };
      }
      case 'skills/get': {
        const uri = params?.uri;
        if (typeof uri !== 'string') {
          throw new McpError(ErrorCode.InvalidParams, 'skills/get requires a uri');
        }
        const record = findSkillMd(index, uri);
        if (!record) {
          throw new McpError(ErrorCode.InvalidParams, `Unknown skill URI: ${uri}`);
        }
        return {
          skill: skillEntry(record),
          ...resultType(state.version),
          ...cacheFields(state.version, SKILLS_TTL_MS, 'public'),
        };
      }
      case 'resources/list': {
        const page = listResources(index, params?.cursor as string | undefined);
        return {
          resources: page.resources,
          ...(page.nextCursor ? { nextCursor: page.nextCursor } : {}),
          ...resultType(state.version),
          ...cacheFields(state.version, SKILLS_TTL_MS, 'public'),
        };
      }
      case 'resources/read': {
        const uri = params?.uri;
        if (typeof uri !== 'string') {
          throw new McpError(ErrorCode.InvalidParams, 'resources/read requires a uri');
        }
        try {
          const file = readSkillFile(root, index, uri);
          const contents = [
            {
              uri,
              mimeType: file.mime,
              ...(isTextual(file.mime)
                ? { text: file.bytes.toString('utf-8') }
                : { blob: file.bytes.toString('base64') }),
            },
          ];
          return {
            contents,
            ...resultType(state.version),
            ...cacheFields(state.version, SKILLS_TTL_MS, 'public'),
          };
        } catch (e) {
          if (e instanceof SkillError) {
            throw new McpError(ErrorCode.InvalidParams, e.message);
          }
          throw e;
        }
      }
      case 'resources/directory/read': {
        const uri = params?.uri;
        if (typeof uri !== 'string') {
          throw new McpError(
            ErrorCode.InvalidParams,
            'resources/directory/read requires a uri',
          );
        }
        try {
          const resources = readSkillDirectory(index, uri);
          return {
            resources,
            ...resultType(state.version),
            ...cacheFields(state.version, SKILLS_TTL_MS, 'public'),
          };
        } catch (e) {
          if (e instanceof SkillError) {
            throw new McpError(ErrorCode.InvalidParams, e.message);
          }
          throw e;
        }
      }
      default:
        return undefined;
    }
  };

  server.fallbackRequestHandler = async (request, extra) => {
    if (state.current) {
      const params = request.params as Record<string, unknown> | undefined;
      const result = await answer(request.method, params);
      if (result !== undefined) return result;
    }
    if (existingFallback) {
      return existingFallback(request, extra);
    }
    throw new McpError(ErrorCode.MethodNotFound, `Method not found: ${request.method}`);
  };
}

/**
 * Is this MIME type text?
 *
 * Text is served as `text`, everything else as `blob`. A client reads
 * `text` into the model's context; `blob` is base64 and is decoded by
 * the client. Serving a PNG as `text` would corrupt it, and serving a
 * markdown file as `blob` would make the client decode it needlessly.
 */
function isTextual(mime: string): boolean {
  return mime.startsWith('text/') || mime === 'application/json' ||
    mime === 'application/yaml' || mime === 'application/xml' ||
    mime === 'image/svg+xml';
}

/**
 * The shape of a tool as it appears in a `tools/list` result.
 *
 * Only the parts this file touches are described; the SDK's own
 * fields pass through untouched.
 */
interface ToolLike {
  name?: string;
  inputSchema?: Record<string, unknown>;
  [key: string]: unknown;
}

/**
 * Add the `cursor` argument to `search_library`'s schema.
 *
 * Under `2026-07-28` pagination is cursor-based, so the argument has
 * to be in the schema or a client cannot use it. It is optional: a
 * cursor is only present on the second page and after.
 */
function withCursorArgument(tool: ToolLike): ToolLike {
  if (tool.name !== 'search_library') return tool;
  const schema = tool.inputSchema;
  if (!schema || typeof schema !== 'object') return tool;
  const properties = (schema.properties ?? {}) as Record<string, unknown>;
  if ('cursor' in properties) return tool;
  return {
    ...tool,
    inputSchema: {
      ...schema,
      properties: {
        ...properties,
        cursor: {
          type: 'string',
          description:
            'The cursor from the previous page. Omit for the first page.',
        },
      },
    },
  };
}

/**
 * Add the revision-gated fields to `tools/list` and `tools/call`.
 *
 * `2026-07-28` requires `ttlMs` and `cacheScope` on list results, and
 * `resultType` on every result. The older revision requires none of
 * them, and gets none of them -- the fields are absent, not set to a
 * default, so a client on the older revision never finds a field it
 * has not heard of.
 *
 * The newer revision also paginates by cursor, so its `search_library`
 * schema gains a `cursor` argument. The older revision does not have
 * it: a client reading the old revision must not find a field it has
 * never heard of, and the agreement gate compares the tool list byte
 * for byte -- so the argument is added only for the revision that
 * requires it.
 *
 * The SDK's own handlers are *wrapped*, not replaced: the SDK knows
 * how to list the registered tools and how to run one, and that
 * knowledge is not reimplemented here. Only the fields are added.
 *
 * The tool list changes when the library changes -- a new skill does
 * not add a tool, but a new harness does -- so the TTL is short. It is
 * a cache, not a snapshot.
 */
export function installRevisionResultFields(server: Server, state: RevisionState): void {
  const handlers = (server as unknown as {
    _requestHandlers?: Map<string, (request: unknown, extra: unknown) => unknown>;
  })._requestHandlers;
  if (!handlers) return;

  // `tools/list`. The SDK's handler is synchronous; the wrapper is
  // allowed to be async, so it awaits whatever the original returned.
  const listOriginal = handlers.get('tools/list');
  if (listOriginal) {
    handlers.set('tools/list', async (request, extra) => {
      const result = (await listOriginal(request, extra)) as Record<string, unknown>;
      const tools = Array.isArray(result.tools) ? (result.tools as ToolLike[]) : [];
      const patched = isCurrent(state.version) ? tools.map(withCursorArgument) : tools;
      return {
        ...result,
        tools: patched,
        ...cacheFields(state.version, TOOLS_LIST_TTL_MS, 'public'),
      };
    });
  }

  // `tools/call`. A tool that errors still returns a result -- an
  // error is a result with `isError` set, not a protocol error -- so
  // `resultType` goes on both.
  const callOriginal = handlers.get('tools/call');
  if (callOriginal) {
    handlers.set('tools/call', async (request, extra) => {
      const result = (await callOriginal(request, extra)) as Record<string, unknown>;
      return { ...result, ...resultType(state.version) };
    });
  }
}
