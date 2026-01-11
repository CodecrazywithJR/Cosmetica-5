'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import {
  getInstagramPosts,
  generateInstagramPack,
  downloadInstagramPack,
  InstagramPost,
} from '@/lib/social';

export default function SocialPage() {
  const t = useTranslations();
  const [posts, setPosts] = useState<InstagramPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatingPack, setGeneratingPack] = useState<number | null>(null);

  const loadPosts = async () => {
    try {
      setLoading(true);
      const data = await getInstagramPosts();
      setPosts(data);
    } catch (err: any) {
      console.error('Error loading posts:', err);
      setError(err.response?.data?.detail || 'Failed to load posts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPosts();
  }, []);

  const handleGeneratePack = async (postId: number) => {
    try {
      setGeneratingPack(postId);
      const result = await generateInstagramPack(postId);
      alert(`Pack generation started! Task ID: ${result.task_id}`);
      // Reload posts to see updated status
      await loadPosts();
    } catch (err: any) {
      console.error('Error generating pack:', err);
      alert(err.response?.data?.error || 'Failed to generate pack');
    } finally {
      setGeneratingPack(null);
    }
  };

  const handleDownloadPack = async (postId: number) => {
    try {
      const blob = await downloadInstagramPack(postId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `instagram_pack_${postId}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      console.error('Error downloading pack:', err);
      alert(err.response?.data?.error || 'Failed to download pack');
    }
  };

  const getStatusBadge = (status: string) => {
    const baseClasses = 'px-3 py-1 rounded-full text-xs font-semibold';
    switch (status) {
      case 'draft':
        return `${baseClasses} bg-gray-100 text-gray-800`;
      case 'ready':
        return `${baseClasses} bg-blue-100 text-blue-800`;
      case 'published':
        return `${baseClasses} bg-green-100 text-green-800`;
      case 'archived':
        return `${baseClasses} bg-yellow-100 text-yellow-800`;
      default:
        return `${baseClasses} bg-gray-100 text-gray-800`;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-8">Instagram Management</h1>
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-600">Loading posts...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-8">Instagram Management</h1>
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <p className="text-red-800 font-semibold">Error loading posts</p>
            <p className="text-red-600 mt-2">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold">Instagram Management</h1>
            <p className="text-gray-600 mt-1">Manual Publish Pack Workflow</p>
          </div>
          <a
            href="/admin/social/instagrampost/add/"
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
          >
            Create New Post
          </a>
        </div>

        {/* Info Banner */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <h3 className="font-semibold text-blue-900 mb-2">📱 Manual Publish Workflow</h3>
          <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
            <li>Create post in Django Admin with caption and media from marketing bucket</li>
            <li>Generate publish pack (ZIP file)</li>
            <li>Download ZIP and extract files</li>
            <li>Open Instagram app on your phone</li>
            <li>Create new post with images from ZIP</li>
            <li>Copy caption from caption.txt</li>
            <li>Publish on Instagram</li>
            <li>Mark post as published in admin with Instagram URL</li>
          </ol>
        </div>

        {/* Posts List */}
        {posts.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-600">No posts yet. Create your first post in Django Admin.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {posts.map((post) => (
              <div key={post.id} className="bg-white rounded-lg shadow p-6">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold">Post #{post.id}</h3>
                      <span className={getStatusBadge(post.status)}>{post.status}</span>
                      <span className="text-sm text-gray-500">
                        {post.language.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-gray-700 mb-2">
                      {post.caption.substring(0, 150)}
                      {post.caption.length > 150 ? '...' : ''}
                    </p>
                    {post.hashtags.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-2">
                        {post.hashtags.map((tag, idx) => (
                          <span
                            key={idx}
                            className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-4 text-sm text-gray-600 mt-3">
                      <span>📸 {post.media_count} media</span>
                      <span>👤 {post.created_by_username}</span>
                      <span>📅 {new Date(post.created_at).toLocaleDateString()}</span>
                      {post.published_at && (
                        <span>✅ Published {new Date(post.published_at).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-3 mt-4 pt-4 border-t">
                  {post.can_generate_pack && (
                    <button
                      onClick={() => handleGeneratePack(post.id)}
                      disabled={generatingPack === post.id}
                      className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                      {generatingPack === post.id ? 'Generating...' : '📦 Generate Pack'}
                    </button>
                  )}
                  {post.pack_file_path && (
                    <button
                      onClick={() => handleDownloadPack(post.id)}
                      className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
                    >
                      ⬇️ Download Pack
                    </button>
                  )}
                  <a
                    href={`/admin/social/instagrampost/${post.id}/change/`}
                    className="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
                  >
                    ✏️ Edit
                  </a>
                  {post.instagram_url && (
                    <a
                      href={post.instagram_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700"
                    >
                      📱 View on Instagram
                    </a>
                  )}
                </div>

                {/* Pack Info */}
                {post.pack_generated_at && (
                  <div className="mt-4 p-3 bg-gray-50 rounded text-sm">
                    <p className="text-gray-600">
                      Pack generated: {new Date(post.pack_generated_at).toLocaleString()}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
