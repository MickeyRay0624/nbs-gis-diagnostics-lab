import { useState } from "react";

export function FileUpload({ id, label, accept, fileName, onChange }: {
  id?: string; label: string; accept: string; fileName?: string;
  onChange: (file?: File) => void;
}) {
  const [selectedName, setSelectedName] = useState("");
  return <div className="file-upload">
    <span className="file-choose" aria-hidden="true">Choose file</span>
    <span className="file-name" aria-hidden="true" title={fileName ?? selectedName}>{(fileName ?? selectedName) || "No file selected"}</span>
    <input id={id} aria-label={label} aria-description={(fileName ?? selectedName) || "No file selected"} type="file" accept={accept} onChange={event => {
      const file = event.target.files?.[0];
      if (!file) return;
      setSelectedName(file.name); onChange(file);
      // Clearing the native value lets the same file be selected again after removal.
      event.target.value = "";
    }} />
  </div>;
}
