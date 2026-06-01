import { useState, useCallback, useEffect } from "react";
import { Image, X, Upload } from "lucide-react";

export interface PastedImage {
  id: string;
  file: File;
  preview: string;
  uploaded?: boolean;
}

interface ImagePasteHandlerProps {
  onImagesPasted: (images: PastedImage[]) => void;
  images: PastedImage[];
  onRemoveImage: (id: string) => void;
  maxImages?: number;
}

export function ImagePasteHandler({
  onImagesPasted,
  images,
  onRemoveImage,
  maxImages = 5,
}: ImagePasteHandlerProps) {
  const [isDragging, setIsDragging] = useState(false);

  // Handle paste
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      const newImages: PastedImage[] = [];
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) { newImages.push({ id: `img-${crypto.randomUUID()}`, file, preview: URL.createObjectURL(file) }); }
        }
      }
      if (newImages.length > 0) { onImagesPasted([...images, ...newImages].slice(0, maxImages)); }
    };
    window.addEventListener("paste", handlePaste);
    return () => window.removeEventListener("paste", handlePaste);
  }, [images, onImagesPasted, maxImages]);

  // Handle drag & drop
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault(); setIsDragging(false);
      const files = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith("image/"));
      const newImages = files.map((file) => ({ id: `img-${crypto.randomUUID()}`, file, preview: URL.createObjectURL(file) }));
      if (newImages.length > 0) { onImagesPasted([...images, ...newImages].slice(0, maxImages)); }
    },
    [images, onImagesPasted, maxImages]
  );

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className="relative font-mono"
    >
      {/* Drop zone indicator */}
      {isDragging && (
        <div
          className="absolute inset-0 flex items-center justify-center z-50 rounded-sm"
          style={{ background: "var(--c-s2)", border: `1px dashed var(--c-accent)` }}
        >
          <div className="text-center">
            <Upload size={24} className="mx-auto mb-2 block" style={{ color: "var(--c-accent)" }} />
            <span className="text-xs" style={{ color: "var(--c-accent)" }}>Drop images here</span>
          </div>
        </div>
      )}

      {/* Pasted image previews */}
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2">
          {images.map((img) => (
            <div key={img.id} className="relative">
              <img
                src={img.preview}
                alt="Pasted"
                className="w-16 h-16 object-cover border block rounded-sm"
                style={{ borderColor: "var(--c-s3)" }}
              />
              <button
                onClick={() => onRemoveImage(img.id)}
                title="Remove image"
                className="absolute -top-1 -right-1 w-4 h-4 border-none cursor-pointer flex items-center justify-center p-0 opacity-0"
                style={{ background: "var(--c-err)", borderRadius: 0, transition: "opacity 100ms ease" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "1"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.opacity = "0"; }}
              >
                <X size={10} style={{ color: "#fff" }} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Paste hint */}
      {images.length === 0 && (
        <div className="flex items-center gap-1 text-[10px]" style={{ color: "var(--c-text3)" }}>
          <Image size={10} />
          <span>Ctrl+V to paste image</span>
        </div>
      )}
    </div>
  );
}

export default ImagePasteHandler;
