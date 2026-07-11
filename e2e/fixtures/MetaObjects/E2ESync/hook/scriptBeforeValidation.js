// E2ESync: before-validation hook (fixture only — not executed against a live server)
// The sync script reads this file and merges its content into the document meta
// under the key "scriptBeforeValidation" before diffing / applying.
if (!data.title) {
	errors.push("title is required");
}
