"use client";

import { use, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { QuestionType } from "@/lib/types";

interface QuestionOut {
  id: string;
  label: string;
  question_type: QuestionType;
  is_required: boolean;
  sort_order: number;
  options: { id: string; label: string; value: string }[];
}

const QUESTION_TYPES: QuestionType[] = [
  "short_text", "long_text", "email", "phone", "number", "currency", "date", "single_select", "multi_select", "checkbox", "yes_no",
];

const schema = z.object({
  label: z.string().min(1, "Question label is required."),
  question_type: z.enum(QUESTION_TYPES as [QuestionType, ...QuestionType[]]),
  is_required: z.boolean(),
  optionsText: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export default function QualificationFormDetailPage({ params }: { params: Promise<{ formId: string }> }) {
  const { formId } = use(params);
  const queryClient = useQueryClient();

  const questionsQuery = useQuery({
    queryKey: ["qualification-form", formId, "questions"],
    queryFn: () => api.get<QuestionOut[]>(`/tenant/qualification-forms/${formId}/questions`),
  });

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { is_required: false, question_type: "short_text" } });
  const questionType = watch("question_type");

  const createMutation = useMutation({
    mutationFn: (values: FormValues) =>
      api.post(`/tenant/qualification-forms/${formId}/questions`, {
        label: values.label,
        question_type: values.question_type,
        is_required: values.is_required,
        options: values.optionsText ? values.optionsText.split(",").map((s) => s.trim()).filter(Boolean) : [],
      }),
    onSuccess: () => {
      reset({ label: "", is_required: false, question_type: "short_text", optionsText: "" });
      queryClient.invalidateQueries({ queryKey: ["qualification-form", formId, "questions"] });
    },
  });

  const [order, setOrder] = useState<string[] | null>(null);
  const reorderMutation = useMutation({
    mutationFn: (questionIds: string[]) => api.put(`/tenant/qualification-forms/${formId}/questions/reorder`, { question_ids: questionIds }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["qualification-form", formId, "questions"] }),
  });

  const questions = order
    ? order.map((id) => questionsQuery.data?.find((q) => q.id === id)).filter((q): q is QuestionOut => Boolean(q))
    : (questionsQuery.data ?? []);

  function move(index: number, direction: -1 | 1) {
    const current = questions.map((q) => q.id);
    const target = index + direction;
    if (target < 0 || target >= current.length) return;
    const a = current[index];
    const b = current[target];
    if (!a || !b) return;
    current[index] = b;
    current[target] = a;
    setOrder(current);
    reorderMutation.mutate(current);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Questions</h1>
        <p className="mt-1 text-sm text-ink-muted">Editable and reorderable qualification questions for this form.</p>
      </div>

      <Card>
        <CardHeader title="Add a question" />
        <form className="space-y-4" onSubmit={handleSubmit((values) => createMutation.mutate(values))} noValidate>
          {createMutation.isError && (
            <Alert tone="error">{createMutation.error instanceof ApiError ? createMutation.error.message : "Unable to add question."}</Alert>
          )}
          <div>
            <Label htmlFor="label">Question</Label>
            <Input id="label" {...register("label")} />
            <FieldError>{errors.label?.message}</FieldError>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="question_type">Type</Label>
              <select
                id="question_type"
                className="focus-ring w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-ink"
                {...register("question_type")}
              >
                {QUESTION_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            <label className="mt-6 flex items-center gap-2 text-sm text-ink-muted">
              <input type="checkbox" {...register("is_required")} /> Required
            </label>
          </div>
          {(questionType === "single_select" || questionType === "multi_select") && (
            <div>
              <Label htmlFor="optionsText">Options (comma-separated)</Label>
              <Input id="optionsText" placeholder="Option A, Option B, Option C" {...register("optionsText")} />
            </div>
          )}
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Adding…" : "Add question"}
          </Button>
        </form>
      </Card>

      <Card>
        <CardHeader title="Current questions" />
        <div className="space-y-2">
          {questions.map((question, index) => (
            <div key={question.id} className="flex items-center justify-between rounded-md border border-surface-border p-3">
              <div>
                <p className="text-sm text-ink">
                  {question.label} {question.is_required && <span className="text-accent">*</span>}
                </p>
                <p className="text-xs text-ink-faint">{question.question_type.replaceAll("_", " ")}</p>
              </div>
              <div className="flex gap-1">
                <Button variant="ghost" onClick={() => move(index, -1)} disabled={index === 0}>
                  ↑
                </Button>
                <Button variant="ghost" onClick={() => move(index, 1)} disabled={index === questions.length - 1}>
                  ↓
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
