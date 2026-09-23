# History and resume behavior

Stored and displayed conversation history is complete and remains available through the conversation endpoints and sidebar.

The model working context is bounded by `MAX_HISTORY_MESSAGES` (50 by default). When a conversation exceeds that bound, older turns are represented in a bounded summary message and the newest turns are sent individually. This keeps provider requests operationally bounded while retaining older information for resume behavior.
