"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { ActivityItem, AttachmentItem, LeadDetail, NoteItem, TagItem, TaskItem } from "@/lib/types";

export default function LeadDetailPage({ params }: { params: Promise<{ leadId: string }> }) {
  const { leadId } = use(params);
  const queryClient = useQueryClient();
  const [noteBody, setNoteBody] = useState("");
  const [tagName, setTagName] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const leadQuery = useQuery({ queryKey: ["lead", leadId], queryFn: () => api.get<LeadDetail>(`/tenant/leads/${leadId}`) });
  const timelineQuery = useQuery({ queryKey: ["lead", leadId, "timeline"], queryFn: () => api.get<ActivityItem[]>(`/tenant/leads/${leadId}/timeline`) });
  const notesQuery = useQuery({ queryKey: ["lead", leadId, "notes"], queryFn: () => api.get<NoteItem[]>(`/tenant/leads/${leadId}/notes`) });
  const tagsQuery = useQuery({ queryKey: ["lead", leadId, "tags"], queryFn: () => api.get<TagItem[]>(`/tenant/leads/${leadId}/tags`) });
  const tasksQuery = useQuery({ queryKey: ["lead", leadId, "tasks"], queryFn: () => api.get<TaskItem[]>(`/tenant/leads/${leadId}/tasks`) });
  const attachmentsQuery = useQuery({ queryKey: ["lead", leadId, "attachments"], queryFn: () => api.get<AttachmentItem[]>(`/tenant/leads/${leadId}/attachments`) });

  const invalidateLead = () => {
    queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
  };

  const addNote = useMutation({
    mutationFn: () => api.post(`/tenant/leads/${leadId}/notes`, { body: noteBody }),
    onSuccess: () => {
      setNoteBody("");
      invalidateLead();
    },
  });

  const addTag = useMutation({
    mutationFn: () => api.post(`/tenant/leads/${leadId}/tags`, { name: tagName }),
    onSuccess: () => {
      setTagName("");
      invalidateLead();
    },
  });

  const addTask = useMutation({
    mutationFn: () => api.post(`/tenant/leads/${leadId}/tasks`, { title: taskTitle }),
    onSuccess: () => {
      setTaskTitle("");
      invalidateLead();
    },
  });

  const completeTask = useMutation({
    mutationFn: (taskId: string) => api.post(`/tenant/tasks/${taskId}/complete`),
    onSuccess: invalidateLead,
  });

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api"}/tenant/leads/${leadId}/attachments`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error?.message ?? "Upload failed.");
      }
      invalidateLead();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  if (leadQuery.isLoading) return <p className="text-sm text-ink-muted">Loading…</p>;
  const lead = leadQuery.data;
  if (!lead) return <Alert tone="error">Lead not found.</Alert>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">
          {lead.first_name} {lead.last_name}
        </h1>
        <p className="mt-1 text-sm text-ink-muted">{lead.reference_number}</p>
        {lead.is_possible_duplicate && (
          <div className="mt-2">
            <Alert tone="warning">This lead was flagged as a possible duplicate.</Alert>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title="Details" />
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-ink-faint">Email</dt>
                <dd className="text-ink">{lead.email ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Phone</dt>
                <dd className="text-ink">{lead.phone ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Company</dt>
                <dd className="text-ink">{lead.company ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Priority</dt>
                <dd className="capitalize text-ink">{lead.priority}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Preferred contact</dt>
                <dd className="capitalize text-ink">{lead.preferred_contact_method ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Consent</dt>
                <dd className="capitalize text-ink">{lead.consent_status}</dd>
              </div>
            </dl>
          </Card>

          <Card>
            <CardHeader title="Notes" />
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input placeholder="Add a note…" value={noteBody} onChange={(e) => setNoteBody(e.target.value)} />
                <Button onClick={() => addNote.mutate()} disabled={!noteBody.trim() || addNote.isPending}>
                  Add
                </Button>
              </div>
              {notesQuery.data?.map((note) => (
                <div key={note.id} className="rounded-md border border-surface-border p-3 text-sm">
                  <p className="text-ink">{note.body}</p>
                  <p className="mt-1 text-xs text-ink-faint">{new Date(note.created_at).toLocaleString()}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Tasks" />
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input placeholder="New task title…" value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} />
                <Button onClick={() => addTask.mutate()} disabled={!taskTitle.trim() || addTask.isPending}>
                  Add
                </Button>
              </div>
              {tasksQuery.data?.map((task) => (
                <div key={task.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
                  <div>
                    <p className={task.status === "completed" ? "text-ink-faint line-through" : "text-ink"}>{task.title}</p>
                    {task.due_at && <p className="text-xs text-ink-faint">Due {new Date(task.due_at).toLocaleString()}</p>}
                  </div>
                  {task.status === "open" && (
                    <Button variant="secondary" onClick={() => completeTask.mutate(task.id)}>
                      Complete
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Attachments" />
            <div className="space-y-3">
              <input type="file" onChange={handleUpload} disabled={uploading} className="text-sm text-ink-muted" />
              {uploadError && <Alert tone="error">{uploadError}</Alert>}
              {attachmentsQuery.data?.map((attachment) => (
                <div key={attachment.id} className="flex items-center justify-between rounded-md border border-surface-border p-3 text-sm">
                  <span className="text-ink">{attachment.file_name}</span>
                  <span className="text-xs text-ink-faint">{(attachment.size_bytes / 1024).toFixed(1)} KB</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Tags" />
            <div className="flex flex-wrap gap-2">
              {tagsQuery.data?.map((tag) => (
                <span key={tag.id} className="rounded-full border border-surface-border px-2.5 py-1 text-xs text-ink">
                  {tag.name}
                </span>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <Input placeholder="Tag name…" value={tagName} onChange={(e) => setTagName(e.target.value)} />
              <Button variant="secondary" onClick={() => addTag.mutate()} disabled={!tagName.trim() || addTag.isPending}>
                Add
              </Button>
            </div>
            {addTag.isError && (
              <div className="mt-2">
                <Alert tone="error">{addTag.error instanceof ApiError ? addTag.error.message : "Unable to add tag."}</Alert>
              </div>
            )}
          </Card>

          <Card>
            <CardHeader title="Activity timeline" />
            <div className="space-y-3">
              {timelineQuery.data?.map((activity) => (
                <div key={activity.id} className="border-l-2 border-surface-border pl-3 text-sm">
                  <p className="text-ink">{activity.summary}</p>
                  <p className="text-xs text-ink-faint">{new Date(activity.created_at).toLocaleString()}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
