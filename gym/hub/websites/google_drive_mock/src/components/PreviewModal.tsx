import React, { useState } from 'react';
import { FileSystemItem } from '../lib/types';
import { X, Download, Share2, Star, Trash2 } from 'lucide-react';
import { useFileSystem } from '../context/FileSystemContext';
import { cn, downloadDriveItem } from '../lib/utils';
import { ShareModal } from './ShareModal';

interface PreviewModalProps {
  item: FileSystemItem | null;
  onClose: () => void;
}

export const PreviewModal = ({ item, onClose }: PreviewModalProps) => {
  const { dispatch } = useFileSystem();
  const [showShare, setShowShare] = useState(false);
  
  if (!item) return null;

  const handleDelete = () => {
    dispatch({ type: 'DELETE_ITEM', payload: { id: item.id } });
    onClose();
  };

  const handleToggleStar = () => {
    dispatch({ type: 'TOGGLE_STAR', payload: { id: item.id } });
  };

  const handleDownload = () => {
    downloadDriveItem(item);
  };

  const renderContent = () => {
    switch (item.type) {
      case 'image':
        return <img src={item.thumbnailUrl ?? undefined} alt={item.name} className="max-w-full max-h-[80vh] object-contain" />;
      case 'pdf':
        return (
          <div className="flex flex-col items-center justify-center h-[80vh] bg-gray-100 w-full rounded-lg">
             <img src={item.thumbnailUrl || `https://picsum.photos/800/600?random=${item.id}`} className="max-w-full max-h-full opacity-80" />
             <p className="mt-4 text-gray-600">PDF Preview Mock</p>
          </div>
        );
      case 'video':
        return (
          <div className="flex items-center justify-center h-[60vh] bg-black w-full rounded-lg text-white">
            Video Player Mock
          </div>
        );
      default:
        return (
          <div className="p-8 bg-white rounded-lg shadow-sm max-w-2xl w-full">
            <h3 className="text-xl font-bold mb-4">{item.name}</h3>
            <p className="text-gray-600 whitespace-pre-wrap">
              {item.content || "This is a preview of the file content. In a real application, the text content would be fetched and displayed here."}
            </p>
          </div>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex flex-col">
      <div className="h-16 flex items-center justify-between px-4 text-white">
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full">
            <X className="w-6 h-6" />
          </button>
          <span className="font-medium truncate max-w-md">{item.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleToggleStar} className="p-2 hover:bg-white/10 rounded-full">
            <Star className={cn("w-5 h-5", item.starred && "fill-yellow-400 text-yellow-400")} />
          </button>
          <button onClick={handleDelete} className="p-2 hover:bg-white/10 rounded-full">
            <Trash2 className="w-5 h-5" />
          </button>
          <button onClick={() => setShowShare(true)} className="p-2 hover:bg-white/10 rounded-full">
            <Share2 className="w-5 h-5" />
          </button>
          <button onClick={handleDownload} className="px-4 py-2 bg-primary hover:bg-blue-600 rounded text-sm font-medium flex items-center gap-2">
            <Download className="w-4 h-4" />
            Download
          </button>
        </div>
      </div>
      
      <div className="flex-1 flex items-center justify-center p-8 overflow-auto">
        {renderContent()}
      </div>

      {showShare && (
        <ShareModal
          isOpen={true}
          item={item}
          onClose={() => setShowShare(false)}
        />
      )}
    </div>
  );
};
