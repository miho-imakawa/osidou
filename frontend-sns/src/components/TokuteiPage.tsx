// src/components/TokuteiPage.tsx
const TokuteiPage: React.FC = () => {
  const items = [
    { label: "販売業者", value: "今川 美朋" },
    { label: "運営責任者", value: "今川 美朋" },
    { label: "所在地", value: "〒170-0013 東京都豊島区東池袋2丁目62番8号BIGオフィスプラザ池袋1206" },
    { label: "電話番号", value: "請求があれば開示します" },

    { label: "メールアドレス", value: "system@machistrategist.com" },
    { label: "販売価格", value: "各サービスページに表示の価格（200円〜）" },
    { label: "代金の支払い", value: "クレジットカード決済（Stripe）" },
    { label: "商品の引渡時期", value: "決済完了後、即時（ダウンロード、掲載枠が有効化）" },
    { label: "返品・交換・キャンセル", value: "デジタルコンテンツおよびサービスの性質上、決済完了後の返品・返金・キャンセルには応じられません。" },
  ];

  return (
    <div className="max-w-2xl mx-auto py-12 px-4">
      <h1 className="text-2xl font-bold text-gray-800 mb-8">特定商取引法に基づく表記</h1>
      <table className="w-full border-collapse text-sm">
        <tbody>
          {items.map(({ label, value }) => (
            <tr key={label} className="border-t border-gray-200">
              <th className="text-left py-4 pr-6 text-gray-500 font-medium w-40 align-top whitespace-nowrap">
                {label}
              </th>
              <td className="py-4 text-gray-800">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default TokuteiPage;