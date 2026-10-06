import { useState, useMemo } from 'react'
import type { PromptMap as PromptMapType } from '../lib/types'

interface PromptMapProps {
  promptMap: PromptMapType
  candidateId: string
  runId: string
}

export function PromptMap({ promptMap, candidateId }: PromptMapProps) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null)

  const files = useMemo(() => Object.keys(promptMap), [promptMap])

  // Select first file by default
  const currentFile = selectedFile || files[0]
  const fileData = currentFile ? promptMap[currentFile] : null

  if (!fileData) {
    return (
      <div className="text-sm text-[var(--muted)]">No prompt map data available for {candidateId}</div>
    )
  }

  const maxLines = Math.max(...files.map(f => promptMap[f].lines))
  const totalBytes = files.reduce((sum, f) => sum + promptMap[f].bytes, 0)

  // Calculate scale for visual representation
  const getHeight = (lines: number) => {
    const minHeight = 40
    const maxHeight = 400
    return Math.max(minHeight, (lines / maxLines) * maxHeight)
  }

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  }

  return (
    <div className="space-y-4">
      {/* File selector tabs */}
      {files.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          {files.map(file => (
            <button
              key={file}
              onClick={() => setSelectedFile(file)}
              className={`px-3 py-1.5 text-sm rounded border transition-colors ${
                currentFile === file
                  ? 'bg-[var(--primary-soft)] text-[var(--primary)] border-transparent'
                  : 'bg-[var(--surface-2)] text-[var(--muted-strong)] border-[var(--border)] hover:border-[var(--border-strong)]'
              }`}
            >
              {file}
            </button>
          ))}
        </div>
      )}

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] gap-4">
        {/* Left: File columns to scale */}
        <div>
          <h3 className="text-sm font-semibold mb-3 text-[var(--muted-strong)]">
            Files ({files.length})
          </h3>
          <div className="flex gap-3 items-end">
            {files.map(file => {
              const data = promptMap[file]
              const height = getHeight(data.lines)
              const hasChanges = data.add.length > 0 || data.rem.length > 0
              const isSelected = file === currentFile

              return (
                <div
                  key={file}
                  className="flex-1 min-w-[80px] cursor-pointer"
                  onClick={() => setSelectedFile(file)}
                >
                  <div
                    className={`relative border rounded transition-all ${
                      isSelected
                        ? 'border-[var(--primary)] bg-[var(--primary-soft)]'
                        : hasChanges
                          ? 'border-[var(--accent)] border-opacity-40 bg-[var(--surface-2)]'
                          : 'border-[var(--border)] bg-[var(--surface-2)]'
                    }`}
                    style={{ height: `${height}px` }}
                  >
                    {/* Added lines markers */}
                    {data.add.length > 0 && (
                      <div className="absolute inset-0 overflow-hidden">
                        {data.add.map(line => {
                          const pos = (line / data.lines) * 100
                          return (
                            <div
                              key={line}
                              className="absolute left-0 right-0 h-[2px] bg-[var(--accepted)]"
                              style={{ top: `${pos}%` }}
                            />
                          )
                        })}
                      </div>
                    )}

                    {/* Removed lines markers */}
                    {data.rem.length > 0 && (
                      <div className="absolute inset-0 overflow-hidden">
                        {data.rem.map(line => {
                          const pos = (line / data.lines) * 100
                          return (
                            <div
                              key={line}
                              className="absolute left-0 right-0 h-[2px] bg-[var(--rejected)]"
                              style={{ top: `${pos}%` }}
                            />
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {/* File info */}
                  <div className="mt-2 text-center">
                    <div className="text-xs font-mono font-semibold truncate">{file}</div>
                    <div className="text-[10px] text-[var(--muted)] mt-0.5">
                      {data.lines} lines · {formatBytes(data.bytes)}
                    </div>
                    {hasChanges && (
                      <div className="text-[10px] text-[var(--accent)] mt-0.5">
                        +{data.add.length} -{data.rem.length}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Legend */}
          <div className="mt-4 flex gap-4 text-xs text-[var(--muted)]">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-[var(--accepted)]" />
              added lines
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-[var(--rejected)]" />
              removed lines
            </span>
          </div>
        </div>

        {/* Right: Section map for selected file */}
        <div>
          <h3 className="text-sm font-semibold mb-3 text-[var(--muted-strong)]">
            Section map: {currentFile}
          </h3>

          {fileData.headings.length > 0 ? (
            <div className="space-y-2 max-h-[500px] overflow-auto">
              {fileData.headings.map(([line, level, text], idx) => {
                const isTouched = fileData.touched.some(([t]) => t === text)
                const hasAddNearby = fileData.add.some(l => Math.abs(l - line) <= 5)
                const hasRemNearby = fileData.rem.some(l => Math.abs(l - line) <= 5)

                return (
                  <div
                    key={idx}
                    className={`p-2 rounded border transition-all ${
                      isTouched
                        ? 'border-[var(--accent)] bg-[var(--accent)] bg-opacity-10'
                        : 'border-[var(--border)] bg-[var(--surface-2)]'
                    }`}
                    style={{ paddingLeft: `${level * 12 + 8}px` }}
                  >
                    <div className="flex items-start gap-2">
                      <span className="font-mono text-[10px] text-[var(--muted)] mt-0.5">
                        {line}
                      </span>
                      <span className="text-sm flex-1">{text}</span>
                      {isTouched && (
                        <span className="text-[10px] text-[var(--accent)] font-semibold uppercase">
                          touched
                        </span>
                      )}
                    </div>
                    {(hasAddNearby || hasRemNearby) && (
                      <div className="flex gap-2 mt-1 text-[10px]">
                        {hasAddNearby && <span className="text-[var(--accepted)]">+ nearby</span>}
                        {hasRemNearby && <span className="text-[var(--rejected)]">- nearby</span>}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-sm text-[var(--muted)]">No headings found in {currentFile}</div>
          )}

          {/* Summary stats */}
          <div className="mt-4 p-3 bg-[var(--surface-2)] border border-[var(--border)] rounded-lg">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-[var(--muted)] text-xs">Total lines</div>
                <div className="font-mono font-semibold">{fileData.lines}</div>
              </div>
              <div>
                <div className="text-[var(--muted)] text-xs">File size</div>
                <div className="font-mono font-semibold">{formatBytes(fileData.bytes)}</div>
              </div>
              <div>
                <div className="text-[var(--muted)] text-xs">Sections</div>
                <div className="font-mono font-semibold">{fileData.headings.length}</div>
              </div>
              <div>
                <div className="text-[var(--muted)] text-xs">Touched</div>
                <div className="font-mono font-semibold">{fileData.touched.length}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Overall summary */}
      <div className="mt-4 p-3 bg-[var(--surface-2)] border border-[var(--border)] rounded-lg">
        <div className="text-sm font-semibold mb-2">Candidate {candidateId} summary</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <div className="text-[var(--muted)] text-xs">Total files</div>
            <div className="font-mono font-semibold">{files.length}</div>
          </div>
          <div>
            <div className="text-[var(--muted)] text-xs">Total lines</div>
            <div className="font-mono font-semibold">
              {files.reduce((sum, f) => sum + promptMap[f].lines, 0)}
            </div>
          </div>
          <div>
            <div className="text-[var(--muted)] text-xs">Total size</div>
            <div className="font-mono font-semibold">{formatBytes(totalBytes)}</div>
          </div>
          <div>
            <div className="text-[var(--muted)] text-xs">Changes</div>
            <div className="font-mono font-semibold">
              +{files.reduce((sum, f) => sum + promptMap[f].add.length, 0)} -
              {files.reduce((sum, f) => sum + promptMap[f].rem.length, 0)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}