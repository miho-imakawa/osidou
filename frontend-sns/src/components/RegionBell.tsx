// frontend-sns/src/components/RegionBell.tsx

export const RegionBell = ({ count }: { count: number }) => {
  const getRank = (n: number) => {
    if (n >= 100) return { color: "text-yellow-400", label: "ゴールド", bg: "bg-yellow-50" };
    if (n >= 50)  return { color: "text-slate-400",  label: "シルバー", bg: "bg-slate-50" };
    if (n >= 10)  return { color: "text-orange-600", label: "ブロンズ", bg: "bg-orange-50" };
    return { color: "text-gray-300", label: "ノーマル", bg: "bg-gray-50" };
  };

  const rank = getRank(count);

  return (
    <div className="flex flex-col">
    <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
        Area Statistics
    </span>
    <div className="text-sm text-gray-700">
        {/* 💡 表記を変更 */}
        エリア内登録者数：<span className="font-bold text-pink-600">{count}</span> 人
    </div>
    </div>
  );
};