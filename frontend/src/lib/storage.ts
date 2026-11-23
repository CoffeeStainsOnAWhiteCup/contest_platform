type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const memory = new Map<string, string>();

const memoryStorage: StorageLike = {
  getItem: (key) => memory.get(key) ?? null,
  setItem: (key, value) => {
    memory.set(key, value);
  },
  removeItem: (key) => {
    memory.delete(key);
  },
};

function detectStorage(): StorageLike {
  try {
    if (globalThis.localStorage) {
      return globalThis.localStorage;
    }
  } catch {
    // Access to localStorage can throw in privacy modes.
  }
  return memoryStorage;
}

/** localStorage when available, otherwise an in-memory fallback (SSR, tests). */
export const storage: StorageLike = detectStorage();
