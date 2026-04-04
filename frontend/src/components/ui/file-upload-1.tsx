import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { FileSpreadsheet, Upload, X } from "lucide-react";

export default function FileUpload05() {
  return (
    <div className="sm:mx-auto sm:max-w-lg flex items-center justify-center p-10 w-full max-w-lg">
      <form className="w-full bg-white/10 backdrop-blur-xl border border-white/20 p-8 rounded-3xl shadow-2xl transition-all hover:shadow-white/5">
        <h3 className="text-xl font-bold text-white mb-2">File Upload</h3>
        <div className="mt-4 flex justify-center space-x-4 rounded-xl border border-dashed border-white/20 px-6 py-10 transition-colors hover:border-white/40 hover:bg-white/5">
          <div className="sm:flex sm:items-center sm:gap-x-3">
            <Upload
              className="mx-auto h-8 w-8 text-white/40 sm:mx-0 sm:h-6 sm:w-6"
              aria-hidden={true}
            />
            <div className="mt-4 flex text-sm leading-6 text-white/60 sm:mt-0 font-medium">
              <Label
                htmlFor="file-upload-4"
                className="relative cursor-pointer rounded-sm pl-1 text-white hover:underline hover:underline-offset-4 decoration-white/30"
              >
                <span> Drag and drop or choose file to upload </span>
                <input
                  id="file-upload-4"
                  name="file-upload-4"
                  type="file"
                  className="sr-only"
                />
              </Label>
            </div>
          </div>
        </div>
        <p className="mt-2 flex items-center justify-between text-[11px] leading-5 text-white/40 uppercase tracking-wider">
          Max size: 10 MB • Types: XLSX, XLS, CSV
        </p>
        <div className="relative mt-8 rounded-2xl bg-white/5 p-4 border border-white/10">
          <div className="absolute right-2 top-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="rounded-full h-8 w-8 p-0 text-white/40 hover:text-white hover:bg-white/10"
              aria-label="Remove"
            >
              <X className="size-4 shrink-0" aria-hidden={true} />
            </Button>
          </div>
          <div className="flex items-center space-x-4">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/10 shadow-sm ring-1 ring-inset ring-white/20">
              <FileSpreadsheet
                className="size-6 text-white"
                aria-hidden={true}
              />
            </span>
            <div className="w-full min-w-0">
              <p className="text-sm font-semibold text-white truncate">
                Revenue_Q1_2024.xlsx
              </p>
              <p className="mt-1 flex justify-between text-[11px] text-white/40 font-medium">
                <span>3.1 MB</span>
                <span className="text-emerald-400">Completed</span>
              </p>
            </div>
          </div>
        </div>
        <div className="mt-8 flex items-center justify-end space-x-3">
          <Button
            type="button"
            variant="outline"
            className="rounded-xl border-white/20 bg-transparent px-6 py-2 text-sm font-semibold text-white hover:bg-white/10 hover:text-white transition-all transform active:scale-95"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            className="rounded-xl bg-white px-6 py-2 text-sm font-bold text-black shadow-lg shadow-white/10 hover:bg-white/90 transition-all transform active:scale-95"
          >
            Upload
          </Button>
        </div>
      </form>
    </div>
  );
}
