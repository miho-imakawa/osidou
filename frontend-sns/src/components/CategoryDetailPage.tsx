import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { authApi } from '../api';
import CommunityDetailTemplate from './Communitydetailtemplate';

interface DetailData {
  description: string;
  alias?: string;
  cast: { name: string; role?: string; master_id?: number; master_name?: string }[];
  sections: { label: string; content: string }[];
}

const CategoryDetailPage: React.FC = () => {
  const { categoryId } = useParams<{ categoryId: string }>();
  const navigate = useNavigate();

  const [categoryName, setCategoryName] = useState('');
  const [categoryType, setCategoryType] = useState<'music_group' | 'movie' | 'tv' | 'youtube' | 'person' | 'other'>('other');
  const [memberCount, setMemberCount] = useState(0);
  const [detailData, setDetailData] = useState<DetailData>({ description: '', cast: [], sections: [] });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  useEffect(() => {
    if (!categoryId) return;
    const load = async () => {
      try {
        // カテゴリ情報取得
        const catRes = await authApi.get(`/hobby-categories/categories/${categoryId}`);
        setCategoryName(catRes.data.name);
        setMemberCount(catRes.data.member_count || 0);

        // カテゴリタイプを名前から推定
        const name: string = catRes.data.name.toLowerCase();
        if (name.includes('youtube')) setCategoryType('youtube');
        else if (name.includes('movie') || name.includes('映画')) setCategoryType('movie');
        else if (name.includes('tv') || name.includes('drama') || name.includes('ドラマ')) setCategoryType('tv');
        else if (name.includes('people') || name.includes('人物')) setCategoryType('person');
        else if (name.includes('music') || name.includes('音楽') || name.includes('band')) setCategoryType('music_group');
        else setCategoryType('other');

        // Detail情報取得
        const detailRes = await authApi.get(`/hobby-categories/categories/${categoryId}/detail`);
        setDetailData(detailRes.data);
      } catch (err) {
        console.error('取得エラー:', err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [categoryId]);

  const handleSave = async (data: DetailData) => {
    if (!categoryId) return;
    setSaving(true);
    try {
      await authApi.put(`/hobby-categories/categories/${categoryId}/detail`, data);
      setDetailData(data);
      setSaveMessage('✅ 「Chat Page」へ移動します');
      setTimeout(() => {
        navigate(`/community/${categoryId}`);  // ← 追加
      }, 3500);  // 1秒後にチャット画面へ
    } catch (err) {
      setSaveMessage('❌ 保存に失敗しました');
      setTimeout(() => setSaveMessage(''), 3000);
    } finally {
      setSaving(false);
    }
  };

  const handleNavigateToPeople = (masterId: number) => {
    navigate(`/community/${masterId}`);
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-6 flex items-center justify-center h-[400px]">
        <p className="text-gray-400 italic text-sm">Loading...</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-6">
      {/* ヘッダー */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate(-1)}
          className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-400"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <p className="text-[10px] font-bold text-gray-300 uppercase tracking-widest">Community Detail</p>
          <h1 className="text-lg font-black text-gray-900 tracking-tight">{categoryName}</h1>
        </div>
      </div>

      {/* 保存メッセージ */}
      {saveMessage && (
        <div className="mb-4 px-4 py-2 bg-gray-50 rounded-2xl text-[12px] font-bold text-gray-600 text-center">
          {saveMessage}
        </div>
      )}

      {/* テンプレート本体 */}
      <CommunityDetailTemplate
        categoryId={Number(categoryId)}
        categoryName={categoryName}
        categoryType={categoryType}
        description={detailData.description}
        alias={detailData.alias} 
        cast={detailData.cast}
        memberCount={memberCount}
        onSave={handleSave}
        onNavigateToPeople={handleNavigateToPeople}
      />

      {saving && (
        <div className="mt-4 text-center text-[11px] text-gray-400 italic">保存中...</div>
      )}
    </div>
  );
};

export default CategoryDetailPage;