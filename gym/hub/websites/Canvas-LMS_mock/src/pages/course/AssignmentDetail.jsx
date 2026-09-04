import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Edit3, CheckCircle2, Circle, Calendar, Clock, FileText, Upload, Type, Globe } from 'lucide-react';
import { useAppContext } from '../../context/AppContext';
import './AssignmentDetail.css';

export default function AssignmentDetail() {
  const { courseId, assignmentId } = useParams();
  const navigate = useNavigate();
  const { state, setState } = useAppContext();
  const cid = parseInt(courseId);
  const aid = parseInt(assignmentId);

  const assignment = state.assignments.find(a => a.id === aid && a.course_id === cid);
  const course = state.courses.find(c => c.id === cid);

  if (!assignment) {
    return (
      <div className="assignment-detail-page">
        <h1>Assignment Not Found</h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: '8px' }}>
          This assignment does not exist or has been removed.
        </p>
      </div>
    );
  }

  const assignmentGroup = state.assignmentGroups.find(g => g.id === assignment.assignment_group_id);

  const formatDateTime = (dateStr) => {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const hours = d.getHours();
    const minutes = d.getMinutes();
    const ampm = hours >= 12 ? 'pm' : 'am';
    const h = hours % 12 || 12;
    const m = minutes.toString().padStart(2, '0');
    return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()} at ${h}:${m}${ampm}`;
  };

  const formatSubmissionTypes = (types) => {
    if (!types || types.length === 0) return 'No Submission';
    const typeLabels = {
      'online_text_entry': 'Text Entry',
      'online_upload': 'File Upload',
      'online_url': 'Website URL',
      'online_quiz': 'Online Quiz',
      'on_paper': 'On Paper',
      'none': 'No Submission'
    };
    return types.map(t => typeLabels[t] || t).join(', ');
  };

  const togglePublish = () => {
    setState(prev => ({
      ...prev,
      assignments: prev.assignments.map(a =>
        a.id === aid
          ? { ...a, published: !a.published, workflow_state: a.published ? 'unpublished' : 'published' }
          : a
      )
    }));
  };

  return (
    <div className="assignment-detail-page">
      <div className="assignment-detail-header">
        <div className="assignment-detail-title-row">
          <h1>{assignment.name}</h1>
          <div className="assignment-detail-actions">
            <button
              className="btn btn-secondary"
              onClick={() => navigate(`/courses/${courseId}/assignments/${assignmentId}/edit`)}
            >
              <Edit3 size={16} /> Edit
            </button>
            <button
              className={`btn ${assignment.published ? 'btn-success' : 'btn-secondary'}`}
              onClick={togglePublish}
            >
              {assignment.published
                ? <><CheckCircle2 size={16} /> Published</>
                : <><Circle size={16} /> Unpublished</>
              }
            </button>
          </div>
        </div>
      </div>

      <div className="assignment-detail-body">
        <div className="assignment-detail-main">
          <div className="assignment-detail-meta">
            <div className="detail-meta-row">
              <Calendar size={16} />
              <span className="detail-meta-label">Due:</span>
              <span className="detail-meta-value">{formatDateTime(assignment.due_at)}</span>
            </div>
            <div className="detail-meta-row">
              <FileText size={16} />
              <span className="detail-meta-label">Points:</span>
              <span className="detail-meta-value">{assignment.points_possible}</span>
            </div>
            <div className="detail-meta-row">
              <Upload size={16} />
              <span className="detail-meta-label">Submitting:</span>
              <span className="detail-meta-value">{formatSubmissionTypes(assignment.submission_types)}</span>
            </div>
            {assignment.allowed_extensions && assignment.allowed_extensions.length > 0 && (
              <div className="detail-meta-row">
                <Type size={16} />
                <span className="detail-meta-label">File Types:</span>
                <span className="detail-meta-value">{assignment.allowed_extensions.join(', ')}</span>
              </div>
            )}
          </div>

          <div className="assignment-detail-divider" />

          <div className="assignment-detail-description">
            {assignment.description ? (
              <div dangerouslySetInnerHTML={{ __html: assignment.description }} />
            ) : (
              <p className="no-description">No description provided.</p>
            )}
          </div>

          <div className="assignment-detail-divider" />

          <div className="assignment-submit-section">
            <h3>Submit Assignment</h3>
            <p className="submit-note">
              {assignment.submission_types?.includes('on_paper')
                ? 'This is an on-paper submission. No online submission required.'
                : assignment.submission_types?.includes('online_quiz')
                  ? 'Click "Take Quiz" to begin.'
                  : 'Use the submission form below to submit your work.'
              }
            </p>
            {!assignment.submission_types?.includes('on_paper') &&
             !assignment.submission_types?.includes('online_quiz') && (
              <button className="btn btn-primary">Submit Assignment</button>
            )}
          </div>
        </div>

        <div className="assignment-detail-sidebar">
          <div className="detail-sidebar-section">
            <h4>Assignment Group</h4>
            <p>{assignmentGroup?.name || 'Ungrouped'}</p>
            {assignmentGroup?.weight > 0 && (
              <p className="detail-sidebar-meta">{assignmentGroup.weight}% of total grade</p>
            )}
          </div>

          <div className="detail-sidebar-section">
            <h4>Grade Display</h4>
            <p>{assignment.grading_type === 'points' ? 'Points' : assignment.grading_type}</p>
          </div>

          {assignment.needs_grading_count > 0 && (
            <div className="detail-sidebar-section">
              <h4>Needs Grading</h4>
              <p className="needs-grading-count">{assignment.needs_grading_count} submissions</p>
            </div>
          )}

          <div className="detail-sidebar-section">
            <h4>Status</h4>
            <p className={assignment.published ? 'status-published' : 'status-unpublished'}>
              {assignment.published ? 'Published' : 'Unpublished'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
