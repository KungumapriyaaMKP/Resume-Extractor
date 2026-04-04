import React, { useState, useRef } from 'react'
import { Upload, FileCheck, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import TetrisLoading from './ui/tetris-loader'

export function ResumeUpload() {
  const [file, setFile] = useState<File | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [timeTaken, setTimeTaken] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      if (!selectedFile.name.toLowerCase().endsWith('.zip')) {
        setError('Invalid file type. Please upload a .ZIP file.')
        setFile(null)
        return
      }
      setFile(selectedFile)
      setError(null)
      setSuccess(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return

    setIsProcessing(true)
    setError(null)
    const startTime = performance.now()

    const formData = new FormData()
    formData.append('zipfile', file)

    try {
      const response = await fetch('http://localhost:5000/', {
        method: 'POST',
        body: formData,
      })

      if (response.ok) {
        const endTime = performance.now()
        setTimeTaken(((endTime - startTime) / 1000).toFixed(2))

        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'processed_resumes.xlsx'
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)

        setSuccess(true)
        setFile(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
      } else {
        const errText = await response.text()
        setError(`Error processing files: ${errText}`)
      }
    } catch (err) {
      setError('Network error occurred. Make sure the backend is running.')
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <div className="w-full max-w-xl mx-auto">
      <div 
        className="bg-white/10 backdrop-blur-xl border border-white/20 p-8 rounded-3xl shadow-2xl"
      >
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold text-white mb-2">Resume Extractor</h2>
          <p className="text-white/60">Bulk process 1000+ PDF resumes instantly to Excel</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/20 border border-red-500/50 rounded-xl flex items-center gap-3 text-red-200">
            <AlertCircle className="shrink-0" />
            <p className="text-sm">{error}</p>
          </div>
        )}

        {success && (
          <div className="mb-6 p-4 bg-emerald-500/20 border border-emerald-500/50 rounded-xl text-emerald-200 text-center animate-in fade-in slide-in-from-top-2">
            <p className="font-semibold text-lg">✅ Processing Complete!</p>
            {timeTaken && <p className="text-sm opacity-80">Finished in {timeTaken} seconds</p>}
          </div>
        )}

        {!isProcessing ? (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div
              data-no-trail
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                "group relative border-2 border-dashed rounded-2xl p-10 transition-all cursor-pointer text-center",
                file 
                  ? "border-emerald-500/50 bg-emerald-500/5" 
                  : "border-white/10 hover:border-white/40 hover:bg-white/5"
              )}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".zip"
                className="hidden"
                required
              />
              
              <div className="flex flex-col items-center gap-4">
                {file ? (
                  <>
                    <FileCheck className="w-16 h-16 text-emerald-400" />
                    <div>
                      <p className="text-lg font-medium text-white">{file.name}</p>
                      <p className="text-sm text-white/40">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                  </>
                ) : (
                  <>
                    <Upload className="w-16 h-16 text-white/40 group-hover:text-white/60 transition-colors" />
                    <div>
                      <p className="text-lg font-medium text-white">Click to upload ZIP</p>
                      <p className="text-sm text-white/40 font-mono">or drag and drop here</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={!file}
              className="w-full bg-white text-black font-bold py-4 rounded-2xl hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform active:scale-[0.98] shadow-lg shadow-white/10"
            >
              Process Resumes
            </button>
          </form>
        ) : (
          <div className="py-12 flex flex-col items-center">
            <TetrisLoading size="sm" speed="fast" showLoadingText={false} />
            <h3 className="text-xl font-bold text-white mt-8 mb-2 tracking-tight">Processing Resumes...</h3>
            <p className="text-white/40 max-w-sm mx-auto text-sm text-center">
              Analyzing resumes using NLP. This may take a few minutes for large batches.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
