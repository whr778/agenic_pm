"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

type SessionPayload = {
  authenticated?: boolean;
  role?: string;
};

type UserRow = {
  id: string;
  username: string;
  role: "user" | "admin";
  suspended: boolean;
  createdAt?: string;
};

type CreateUserForm = {
  username: string;
  password: string;
  role: "user" | "admin";
};

type EditUserForm = {
  username: string;
  password: string;
  role: "user" | "admin";
  suspended: boolean;
};

const initialCreateForm: CreateUserForm = {
  username: "",
  password: "",
  role: "user",
};

function formatDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function AdminPage() {
  const router = useRouter();
  const [checkingAccess, setCheckingAccess] = useState(true);
  const [usersLoading, setUsersLoading] = useState(false);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [createForm, setCreateForm] = useState<CreateUserForm>(initialCreateForm);
  const [creating, setCreating] = useState(false);

  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EditUserForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);

  const api = useCallback(async (path: string, init?: RequestInit): Promise<Response> => {
    const response = await fetch(path, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });

    if (!response.ok) {
      const fallback = `Request failed: ${response.status}`;
      let detail = fallback;
      try {
        const payload = (await response.json()) as { detail?: string };
        detail = payload.detail || fallback;
      } catch {
        detail = fallback;
      }
      throw new Error(detail);
    }

    return response;
  }, []);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const response = await api("/api/admin/users", { method: "GET" });
      const payload = (await response.json()) as { users?: UserRow[] };
      setUsers(payload.users ?? []);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load users");
    } finally {
      setUsersLoading(false);
    }
  }, [api]);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const response = await fetch("/api/auth/session", { credentials: "include" });
        const payload = (await response.json()) as SessionPayload;
        const authenticated = Boolean(payload.authenticated);
        const isAdmin = payload.role === "admin";

        if (!authenticated || !isAdmin) {
          router.replace("/");
          return;
        }

        await loadUsers();
      } catch {
        router.replace("/");
      } finally {
        setCheckingAccess(false);
      }
    };

    void bootstrap();
  }, [loadUsers, router]);

  const editableUser = useMemo(
    () => users.find((user) => user.id === editingUserId) ?? null,
    [editingUserId, users]
  );

  const handleCreateUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = createForm.username.trim();
    const password = createForm.password.trim();
    if (!username || !password || creating) {
      return;
    }

    setError(null);
    setSuccess(null);
    setCreating(true);
    try {
      await api("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          username,
          password,
          role: createForm.role,
        }),
      });
      setCreateForm(initialCreateForm);
      setSuccess("User created");
      await loadUsers();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unable to create user");
    } finally {
      setCreating(false);
    }
  };

  const beginEdit = (user: UserRow) => {
    setEditingUserId(user.id);
    setEditForm({
      username: user.username,
      password: "",
      role: user.role,
      suspended: user.suspended,
    });
    setError(null);
    setSuccess(null);
  };

  const cancelEdit = () => {
    setEditingUserId(null);
    setEditForm(null);
  };

  const saveEdit = async () => {
    if (!editingUserId || !editForm || saving) {
      return;
    }

    const payload: Record<string, string | boolean> = {
      username: editForm.username.trim(),
      role: editForm.role,
      suspended: editForm.suspended,
    };
    if (editForm.password.trim()) {
      payload.password = editForm.password.trim();
    }

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await api(`/api/admin/users/${editingUserId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setSuccess("User updated");
      cancelEdit();
      await loadUsers();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to update user");
    } finally {
      setSaving(false);
    }
  };

  const deleteUser = async (user: UserRow) => {
    if (deletingUserId) {
      return;
    }
    if (!window.confirm(`Delete user ${user.username}?`)) {
      return;
    }

    setDeletingUserId(user.id);
    setError(null);
    setSuccess(null);
    try {
      await api(`/api/admin/users/${user.id}`, { method: "DELETE" });
      setSuccess("User deleted");
      await loadUsers();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unable to delete user");
    } finally {
      setDeletingUserId(null);
    }
  };

  if (checkingAccess) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-6">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
          Checking admin access...
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-[1400px] px-6 py-10">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
            Administration
          </p>
          <h1 className="mt-2 font-display text-4xl font-semibold text-[var(--navy-dark)]">
            User Management
          </h1>
        </div>
        <Link
          href="/"
          className="rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
        >
          Back to board
        </Link>
      </header>

      {error ? (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {success}
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <section className="rounded-3xl border border-[var(--stroke)] bg-white p-6 shadow-[var(--shadow)]">
          <h2 className="font-display text-2xl font-semibold text-[var(--navy-dark)]">Create User</h2>
          <form className="mt-5 space-y-4" onSubmit={handleCreateUser}>
            <label className="block text-sm font-semibold text-[var(--navy-dark)]">
              Username
              <input
                value={createForm.username}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, username: event.target.value }))}
                className="mt-2 w-full rounded-xl border border-[var(--stroke)] px-4 py-3 outline-none ring-[var(--primary-blue)]/30 focus:ring"
                autoComplete="username"
              />
            </label>
            <label className="block text-sm font-semibold text-[var(--navy-dark)]">
              Password
              <input
                type="password"
                value={createForm.password}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, password: event.target.value }))}
                className="mt-2 w-full rounded-xl border border-[var(--stroke)] px-4 py-3 outline-none ring-[var(--primary-blue)]/30 focus:ring"
                autoComplete="new-password"
              />
            </label>
            <label className="block text-sm font-semibold text-[var(--navy-dark)]">
              Role
              <select
                value={createForm.role}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, role: event.target.value as "user" | "admin" }))
                }
                className="mt-2 w-full rounded-xl border border-[var(--stroke)] px-4 py-3 outline-none ring-[var(--primary-blue)]/30 focus:ring"
              >
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={creating}
              className="w-full rounded-xl bg-[var(--secondary-purple)] px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {creating ? "Creating..." : "Create user"}
            </button>
          </form>
        </section>

        <section className="overflow-hidden rounded-3xl border border-[var(--stroke)] bg-white shadow-[var(--shadow)]">
          <div className="flex items-center justify-between border-b border-[var(--stroke)] px-6 py-4">
            <h2 className="font-display text-2xl font-semibold text-[var(--navy-dark)]">Users</h2>
            <button
              type="button"
              onClick={() => void loadUsers()}
              className="rounded-full border border-[var(--stroke)] px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-[var(--navy-dark)]"
              disabled={usersLoading}
            >
              Refresh
            </button>
          </div>

          {usersLoading ? (
            <p className="px-6 py-6 text-sm text-[var(--gray-text)]">Loading users...</p>
          ) : users.length === 0 ? (
            <p className="px-6 py-6 text-sm text-[var(--gray-text)]">No users found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse">
                <thead>
                  <tr className="bg-[var(--surface)] text-left text-xs uppercase tracking-[0.12em] text-[var(--gray-text)]">
                    <th className="px-4 py-3">Username</th>
                    <th className="px-4 py-3">Role</th>
                    <th className="px-4 py-3">Suspended</th>
                    <th className="px-4 py-3">Created</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => {
                    const isEditing = editingUserId === user.id && editForm !== null;
                    return (
                      <tr key={user.id} className="border-t border-[var(--stroke)] text-sm text-[var(--navy-dark)]">
                        <td className="px-4 py-3 align-top">
                          {isEditing ? (
                            <input
                              value={editForm.username}
                              onChange={(event) =>
                                setEditForm((prev) =>
                                  prev ? { ...prev, username: event.target.value } : prev
                                )
                              }
                              className="w-full rounded-lg border border-[var(--stroke)] px-2 py-1.5 outline-none ring-[var(--primary-blue)]/30 focus:ring"
                              aria-label={`Edit username for ${user.username}`}
                            />
                          ) : (
                            user.username
                          )}
                        </td>
                        <td className="px-4 py-3 align-top">
                          {isEditing ? (
                            <select
                              value={editForm.role}
                              onChange={(event) =>
                                setEditForm((prev) =>
                                  prev
                                    ? { ...prev, role: event.target.value as "user" | "admin" }
                                    : prev
                                )
                              }
                              className="rounded-lg border border-[var(--stroke)] px-2 py-1.5"
                              aria-label={`Edit role for ${user.username}`}
                            >
                              <option value="user">user</option>
                              <option value="admin">admin</option>
                            </select>
                          ) : (
                            <span className="rounded-full bg-[var(--surface)] px-2 py-1 text-xs font-semibold uppercase tracking-[0.08em]">
                              {user.role}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 align-top">
                          {isEditing ? (
                            <label className="inline-flex items-center gap-2">
                              <input
                                type="checkbox"
                                checked={editForm.suspended}
                                onChange={(event) =>
                                  setEditForm((prev) =>
                                    prev ? { ...prev, suspended: event.target.checked } : prev
                                  )
                                }
                                aria-label={`Edit suspended for ${user.username}`}
                              />
                              <span className="text-xs">Suspended</span>
                            </label>
                          ) : user.suspended ? (
                            <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-red-700">
                              yes
                            </span>
                          ) : (
                            <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-emerald-700">
                              no
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 align-top text-xs text-[var(--gray-text)]">
                          {formatDate(user.createdAt)}
                        </td>
                        <td className="px-4 py-3 align-top">
                          {isEditing ? (
                            <div className="space-y-2">
                              <input
                                type="password"
                                value={editForm.password}
                                onChange={(event) =>
                                  setEditForm((prev) =>
                                    prev ? { ...prev, password: event.target.value } : prev
                                  )
                                }
                                placeholder="New password (optional)"
                                className="w-full rounded-lg border border-[var(--stroke)] px-2 py-1.5 text-xs"
                                aria-label={`Edit password for ${user.username}`}
                              />
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  onClick={() => void saveEdit()}
                                  disabled={saving}
                                  className="rounded-lg bg-[var(--secondary-purple)] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
                                >
                                  Save changes
                                </button>
                                <button
                                  type="button"
                                  onClick={cancelEdit}
                                  className="rounded-lg border border-[var(--stroke)] px-3 py-1.5 text-xs font-semibold"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex gap-2">
                              <button
                                type="button"
                                onClick={() => beginEdit(user)}
                                className="rounded-lg border border-[var(--stroke)] px-3 py-1.5 text-xs font-semibold"
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => void deleteUser(user)}
                                disabled={deletingUserId === user.id}
                                className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 disabled:opacity-60"
                              >
                                Delete
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {editableUser ? (
        <p className="mt-4 text-xs text-[var(--gray-text)]">
          Editing user: <span className="font-semibold text-[var(--navy-dark)]">{editableUser.username}</span>
        </p>
      ) : null}
    </main>
  );
}
