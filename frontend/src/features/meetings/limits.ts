// FE-04: đồng bộ Query(max_length=200) tại backend/app/api/v1/meetings.py.
export const MEETING_SEARCH_MAX_LENGTH = 200

// FE-10: đồng bộ SegmentPatch.text(max_length=5000) của backend.
export const TRANSCRIPT_TEXT_MAX_LENGTH = 5000

// FE-12: SummaryContentOut.key_points/decisions(max_length=50), backend/app/schemas/summary.py.
export const SUMMARY_ITEMS_MAX_COUNT = 50

// FE-12: SummaryContentOut.overview, backend/app/schemas/summary.py.
export const SUMMARY_OVERVIEW_MAX_LENGTH = 5000
// FE-13: ActionItemCreate/ActionItemPatch, backend/app/schemas/action_item.py.
export const TASK_DESCRIPTION_MAX_LENGTH = 1000
export const TASK_ASSIGNEE_NAME_MAX_LENGTH = 100
