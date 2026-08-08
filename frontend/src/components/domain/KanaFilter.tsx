"use client";
const KANA_ROWS = ["あ","か","さ","た","な","は","ま","や","ら","わ","ABC"];

interface Props { selected: string | null; onSelect: (k: string | null) => void; }

export function KanaFilter({ selected, onSelect }: Props) {
  return (
    <div className="flex gap-1 flex-wrap">
      <button
        onClick={() => onSelect(null)}
        className={`px-3 py-1 rounded text-sm ${!selected ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80"}`}
      >全て</button>
      {KANA_ROWS.map((k) => (
        <button key={k} onClick={() => onSelect(k)}
          className={`px-3 py-1 rounded text-sm ${selected === k ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80"}`}
        >{k}</button>
      ))}
    </div>
  );
}
