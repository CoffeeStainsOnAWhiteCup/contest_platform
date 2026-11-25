import CodeMirror from "@uiw/react-codemirror";
import { cpp } from "@codemirror/lang-cpp";
import { java } from "@codemirror/lang-java";
import { python } from "@codemirror/lang-python";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "@/api/errors";
import { createSubmission } from "@/api/submissions";
import type { ContestDetail, Language, ProblemDetail } from "@/api/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/form";
import { LANGUAGE_LABELS, contestStatusLabel } from "@/lib/labels";
import { formatDateTime } from "@/lib/format";
import { submitDenial } from "@/lib/contestWindow";

const TEMPLATES: Record<Language, string> = {
  python: `import sys\n\n\ndef main():\n    data = sys.stdin.read().split()\n    # TODO\n\n\nif __name__ == "__main__":\n    main()\n`,
  cpp: `#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n    // TODO\n    return 0;\n}\n`,
  java: `import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner scanner = new Scanner(System.in);\n        // TODO\n    }\n}\n`,
};

const EXTENSIONS = {
  python: python,
  cpp,
  java,
} as const;

export function SubmitPanel({
  problem,
  contest,
}: {
  problem: ProblemDetail;
  contest: ContestDetail;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [language, setLanguage] = useState<Language>("python");
  const [code, setCode] = useState(TEMPLATES.python);
  const mutation = useMutation({
    mutationFn: () =>
      createSubmission({ problem_id: problem.id, language, code }),
    onSuccess: (submission) => {
      queryClient.setQueryData(["submission", submission.id], submission);
      void queryClient.invalidateQueries({ queryKey: ["submissions"] });
      navigate(`/submissions/${submission.id}`);
    },
  });

  function changeLanguage(next: Language) {
    setLanguage(next);
    setCode(TEMPLATES[next]);
  }

  const denial = submitDenial(contest);
  const canSubmit = contest.can_submit && denial === null;

  return (
    <Card title="Отправка решения">
      <p className="mb-3 text-xs text-muted-foreground">
        Интервал конкурса: {formatDateTime(contest.start_at)} — {formatDateTime(contest.end_at)}
      </p>
      {denial && (
        <Alert variant="info" className="mb-3">
          {denial.kind === "not_active" &&
            `Отправка доступна только в активном конкурсе. Сейчас статус «${contestStatusLabel(
              denial.status,
            )}».`}
          {denial.kind === "not_started" &&
            `Конкурс ещё не начался. Начало: ${formatDateTime(denial.startAt)}.`}
          {denial.kind === "finished" &&
            `Конкурс уже завершился. Окончание: ${formatDateTime(denial.endAt)}.`}
        </Alert>
      )}
      {mutation.isError && (
        <Alert variant="error" className="mb-3">
          {errorMessage(mutation.error)}
        </Alert>
      )}
      <div className="space-y-3">
        <div className="w-48">
          <Label htmlFor="language">Язык</Label>
          <Select
            id="language"
            value={language}
            onChange={(event) => changeLanguage(event.target.value as Language)}
          >
            {(Object.keys(LANGUAGE_LABELS) as Language[]).map((value) => (
              <option key={value} value={value}>
                {LANGUAGE_LABELS[value]}
              </option>
            ))}
          </Select>
        </div>
        <div className="overflow-hidden rounded border border-border">
          <CodeMirror
            value={code}
            height="320px"
            extensions={[EXTENSIONS[language]()]}
            onChange={(value) => setCode(value)}
          />
        </div>
        <Button
          disabled={!canSubmit || mutation.isPending || code.trim().length === 0}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? "Отправляем…" : "Отправить"}
        </Button>
      </div>
    </Card>
  );
}
