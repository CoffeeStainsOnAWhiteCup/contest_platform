import type { Board } from "@/api/types";
import { Pagination } from "@/components/Pagination";

export function Scoreboard({ board, onPage }: { board: Board; onPage: (page: number) => void }) {
  if (board.items.length === 0) {
    return <p className="text-sm text-muted-foreground">Пока нет результатов.</p>;
  }

  return (
    <div className="space-y-3">
      <table className="table">
        <thead>
          <tr>
            <th className="w-16">Место</th>
            <th>Участник</th>
            <th className="w-24">Решено</th>
            <th className="w-24">Штраф</th>
          </tr>
        </thead>
        <tbody>
          {board.items.map((entry) => (
            <tr key={entry.user_id}>
              <td>{entry.place}</td>
              <td>{entry.name}</td>
              <td>{entry.solved}</td>
              <td>{entry.penalty}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination page={board.page} size={board.size} total={board.total} onPage={onPage} />
    </div>
  );
}
