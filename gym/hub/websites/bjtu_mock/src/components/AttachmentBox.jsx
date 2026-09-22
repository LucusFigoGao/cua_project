import React from 'react';
import { useApp } from '../context/AppContext';

export default function AttachmentBox({ parentId, attachments }) {
  const { sid, logDownload } = useApp();
  return (
    <div className="attachment-box">
      <div className="attachment-head">附件下载区</div>
      <ul>
        {attachments.map((att) => (
          <li key={att.id}>
            <a
              className="attachment-link"
              href={`/files/${att.id}?sid=${encodeURIComponent(sid || 'default')}`}
              onClick={() => logDownload(parentId, att)}
            >
              <span className={`att-tag ${att.fileType}`}>[{att.fileType === 'pdf' ? 'PDF' : 'DOC'}]</span>
              <span className="att-name">{att.fileName}</span>
              <span className="att-size">({att.sizeKb}KB)</span>
              <span className="att-dl">下载</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
