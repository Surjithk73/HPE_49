import React, { useState, useEffect, useRef, ChangeEvent } from 'react'
import { Link } from 'react-router-dom'
import JSZip from 'jszip'
import { Database, Upload, Loader2, CheckCircle2, XCircle, AlertCircle, Plus, FileText, X, ArrowLeft, Cpu, Trash2 } from 'lucide-react'
import { getDatabaseDetails, appendMeasureData, uploadMeasureData, deleteDatabase } from '../lib/api'
import type { DatabaseDetails } from '../lib/api'
import { HPELogo } from '../components/HPELogo'
import ThemeToggle from '../components/ThemeToggle'

const STANDARD_TABLES = [
  'cpu', 'dfile', 'disc', 'dopen', 'file', 
  'ossns', 'proc', 'sqlp', 'sqls', 'tmf', 'udef'
]

export default function DatabaseManager() {
  const [details, setDetails] = useState<DatabaseDetails[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const [uploadingDb, setUploadingDb] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<{db: string, msg: string} | null>(null)

  // Create new DB state
  const [showCreate, setShowCreate] = useState(false)
  const [newDbName, setNewDbName] = useState('')
  const [newDbFiles, setNewDbFiles] = useState<File[]>([])
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const [deletingDb, setDeletingDb] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadDetails = async () => {
    try {
      const data = await getDatabaseDetails()
      setDetails(data)
      setError(null)
    } catch (err: any) {
      setError(err.message || 'Failed to load database details')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDetails()
  }, [])

  const handleAppendDrop = async (e: React.DragEvent<HTMLDivElement>, db: string) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await processUpload(e.dataTransfer.files, db)
    }
  }

  const handleAppendSelect = async (e: ChangeEvent<HTMLInputElement>, db: string) => {
    if (e.target.files && e.target.files.length > 0) {
      await processUpload(e.target.files, db)
    }
  }

  const extractFiles = async (fileList: FileList | File[]): Promise<File[]> => {
    const extracted: File[] = []
    for (const file of Array.from(fileList)) {
      if (file.name.toLowerCase().endsWith('.zip')) {
        try {
          const zip = await JSZip.loadAsync(file)
          for (const relativePath in zip.files) {
            const zipEntry = zip.files[relativePath]
            if (!zipEntry.dir && !relativePath.includes('__MACOSX') && !relativePath.includes('.DS_Store')) {
              const blob = await zipEntry.async('blob')
              const filename = relativePath.split('/').pop() || relativePath
              extracted.push(new File([blob], filename, { type: 'text/csv' }))
            }
          }
        } catch (e) {
          console.error('Failed to extract zip:', e)
        }
      } else {
        extracted.push(file)
      }
    }
    return extracted
  }

  const processUpload = async (fileList: FileList | File[], targetDb: string) => {
    try {
      setUploadingDb(targetDb)
      setUploadError(null)
      
      const allFiles = await extractFiles(fileList)
      const dbInfo = details.find(d => d.database === targetDb)
      const existingTables = dbInfo ? dbInfo.tables.map(t => t.toLowerCase()) : []
      const duplicateFileNames: string[] = []
      const filesToUpload: File[] = []
      
      allFiles.forEach(f => {
        const baseName = f.name.toLowerCase().replace(/\.csv$/, '')
        if (existingTables.includes(baseName)) {
           duplicateFileNames.push(f.name)
        } else {
           filesToUpload.push(f)
        }
      })
      
      if (duplicateFileNames.length > 0) {
         setTimeout(() => alert(`Skipped duplicate files already in database: ${duplicateFileNames.join(', ')}`), 10)
      }
      
      if (filesToUpload.length === 0) {
         setUploadingDb(null)
         return
      }

      await appendMeasureData(filesToUpload, targetDb)
      await loadDetails() // refresh after success
    } catch (err: any) {
      setUploadError({ db: targetDb, msg: err.message || 'Upload failed' })
    } finally {
      setUploadingDb(null)
    }
  }

  const handleDeleteDb = async (targetDb: string) => {
    if (!window.confirm(`Are you sure you want to delete the database '${targetDb}' and all its Measure data? This action cannot be undone.`)) {
      return
    }
    setDeletingDb(targetDb)
    try {
      await deleteDatabase(targetDb)
      await loadDetails() // reload the list
    } catch (err: any) {
      setError(err.message || `Failed to delete database ${targetDb}`)
    } finally {
      setDeletingDb(null)
    }
  }

  const handleCreateDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (e.dataTransfer.files) {
      await processCreateFiles(e.dataTransfer.files)
    }
  }

  const handleCreateSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      await processCreateFiles(e.target.files)
    }
  }

  const processCreateFiles = async (fileList: FileList | File[]) => {
    setIsCreating(true)
    const allFiles = await extractFiles(fileList)
    setIsCreating(false)

    setNewDbFiles(prev => {
      const validFiles: File[] = []
      const invalidFileNames: string[] = []
      const duplicateFileNames: string[] = []

      allFiles.forEach(f => {
        const baseName = f.name.toLowerCase().replace(/\.csv$/, '')
        const isStandard = STANDARD_TABLES.includes(baseName) || baseName === 'cpucsv' || baseName === 'disccsv' || baseName === 'proccsv' || baseName === 'filecsv' || baseName === 'dfilecsv' || baseName === 'dopencsv' || baseName === 'ossnscsv' || baseName === 'sqlpcsv' || baseName === 'sqlscsv' || baseName === 'tmfcsv' || baseName === 'udefcsv'
        
        if (isStandard) {
          if (prev.some(existing => existing.name.toLowerCase() === f.name.toLowerCase())) {
            duplicateFileNames.push(f.name)
          } else {
            validFiles.push(f)
          }
        } else {
          invalidFileNames.push(f.name)
        }
      })

      let errorMsg = ''
      if (invalidFileNames.length > 0) errorMsg += `Ignored invalid files: ${invalidFileNames.join(', ')}. `
      if (duplicateFileNames.length > 0) {
        errorMsg += `Skipped duplicates: ${duplicateFileNames.join(', ')}.`
        setTimeout(() => alert(`Skipped duplicate files: ${duplicateFileNames.join(', ')}`), 10)
      }
      setCreateError(errorMsg || null)

      return [...prev, ...validFiles]
    })
  }

  const handleCreateSubmit = async () => {
    if (!newDbName.trim() || newDbFiles.length === 0) return
    
    setIsCreating(true)
    setCreateError(null)
    try {
      await uploadMeasureData(newDbFiles, newDbName.trim())
      await loadDetails()
      setShowCreate(false)
      setNewDbName('')
      setNewDbFiles([])
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create database')
    } finally {
      setIsCreating(false)
    }
  }

  if (loading && details.length === 0) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--theme-bg)', color: 'var(--theme-tx-primary)', fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace' }}>
        <header style={{ borderBottom: '1px solid var(--theme-border)', background: 'var(--theme-surface-1)' }}>
          <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '56px' }}>
            <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <HPELogo width={98} height={28} />
              </div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--theme-tx-primary)', letterSpacing: '-0.02em' }}>QueryCraft</div>
                <div style={{ fontSize: '11px', color: 'var(--theme-tx-secondary)' }}>HPE NonStop Performance Analytics</div>
              </div>
            </Link>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <Link to="/dashboard" style={{ padding: '8px 14px', borderRadius: '8px', background: 'var(--theme-surface-2)', border: '1px solid var(--theme-border-bright)', color: 'var(--theme-tx-primary)', fontSize: '12px', textDecoration: 'none', fontWeight: 600 }}>
                Back to Dashboard
              </Link>
              <ThemeToggle />
            </div>
          </div>
        </header>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '64px', color: 'var(--theme-tx-secondary)' }}>
          <Loader2 className="spinner" size={24} style={{ animation: 'spin 1s linear infinite' }} />
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--theme-bg)', color: 'var(--theme-tx-primary)', fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace' }}>
      <header style={{ borderBottom: '1px solid var(--theme-border)', background: 'var(--theme-surface-1)' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '56px' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <HPELogo width={98} height={28} />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--theme-tx-primary)', letterSpacing: '-0.02em' }}>QueryCraft</div>
              <div style={{ fontSize: '11px', color: 'var(--theme-tx-secondary)' }}>HPE NonStop Performance Analytics</div>
            </div>
          </Link>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <Link to="/dashboard" style={{ padding: '8px 14px', borderRadius: '8px', background: 'var(--theme-surface-2)', border: '1px solid var(--theme-border-bright)', color: 'var(--theme-tx-primary)', fontSize: '12px', textDecoration: 'none', fontWeight: 600 }}>
              Back to Dashboard
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <div style={{ padding: '32px', maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 700, margin: '0 0 8px 0', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Database size={28} color="var(--theme-accent)" />
          Database Manager
        </h1>
        <p style={{ color: 'var(--theme-tx-secondary)', margin: 0 }}>
          View existing nodes, see which Measure files are loaded, and append missing or custom data files directly to a schema.
        </p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '24px' }}>
        <button 
          onClick={() => setShowCreate(!showCreate)}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', background: showCreate ? 'var(--theme-surface-4)' : 'var(--theme-accent)', color: 'var(--theme-tx-primary)', border: 'none', padding: '10px 16px', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '14px' }}
        >
          {showCreate ? <><X size={18} /> Cancel</> : <><Plus size={18} /> Create New Database</>}
        </button>
      </div>

      {showCreate && (
        <div style={{ background: 'var(--theme-surface-1)', border: '1px solid var(--theme-surface-4)', borderRadius: '12px', padding: '24px', marginBottom: '32px' }}>
          <h2 style={{ margin: '0 0 20px', fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Upload size={20} color="var(--theme-accent)" /> Create New Database
          </h2>
          
          {createError && (
            <div style={{ padding: '12px', background: 'rgba(239,68,68,0.1)', color: '#ef4444', borderRadius: '6px', fontSize: '13px', marginBottom: '20px' }}>
              {createError}
            </div>
          )}

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', color: 'var(--theme-tx-primary)' }}>Database Name</label>
            <input 
              type="text" 
              value={newDbName} 
              onChange={e => setNewDbName(e.target.value)} 
              placeholder="e.g. machd600"
              style={{ width: '100%', padding: '10px 14px', background: 'var(--theme-bg)', border: '1px solid var(--theme-border-bright)', borderRadius: '6px', color: 'var(--theme-tx-primary)', outline: 'none' }}
              disabled={isCreating}
            />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '13px', color: 'var(--theme-tx-primary)' }}>Measure Files</label>
            <div 
              onDragOver={e => e.preventDefault()}
              onDrop={handleCreateDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{ border: '2px dashed var(--theme-border-bright)', borderRadius: '8px', padding: '32px', textAlign: 'center', cursor: isCreating ? 'not-allowed' : 'pointer', background: 'var(--theme-bg)' }}
            >
              <Upload size={24} color="var(--theme-tx-muted)" style={{ marginBottom: '12px' }} />
              <div style={{ fontSize: '14px', color: 'var(--theme-tx-primary)' }}>Drag files or ZIP archives here</div>
              <input 
                ref={fileInputRef} type="file" multiple
                onChange={handleCreateSelect} style={{ display: 'none' }} disabled={isCreating}
              />
            </div>
          </div>

          {newDbFiles.length > 0 && (
            <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {newDbFiles.map((f, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--theme-surface-2)', padding: '8px 12px', borderRadius: '6px', fontSize: '13px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><FileText size={14} color="var(--theme-accent)" /> {f.name}</div>
                  <button onClick={() => setNewDbFiles(prev => prev.filter((_, idx) => idx !== i))} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}><X size={14} /></button>
                </li>
              ))}
            </ul>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button 
              onClick={handleCreateSubmit}
              disabled={isCreating || !newDbName.trim() || newDbFiles.length === 0}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--theme-accent)', color: 'var(--theme-tx-primary)', border: 'none', padding: '10px 20px', borderRadius: '8px', cursor: (isCreating || !newDbName.trim() || newDbFiles.length === 0) ? 'not-allowed' : 'pointer', opacity: (isCreating || !newDbName.trim() || newDbFiles.length === 0) ? 0.5 : 1, fontWeight: 600 }}
            >
              {isCreating ? <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Creating...</> : 'Create Database'}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div style={{ padding: '16px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444', borderRadius: '8px', marginBottom: '24px' }}>
          <AlertCircle size={18} style={{ display: 'inline', marginRight: '8px', verticalAlign: 'text-bottom' }} />
          {error}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {details.map(db => {
          const isUploading = uploadingDb === db.database
          const dbError = uploadError?.db === db.database ? uploadError.msg : null

          // Separate standard tables from custom extra tables
          const standardPresent = STANDARD_TABLES.filter(t => db.tables.includes(t))
          const standardMissing = STANDARD_TABLES.filter(t => !db.tables.includes(t))
          const customTables = db.tables.filter(t => !STANDARD_TABLES.includes(t))

          return (
            <div key={db.database} style={{ background: 'var(--theme-surface-1)', border: '1px solid var(--theme-surface-4)', borderRadius: '12px', overflow: 'hidden' }}>
              <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--theme-surface-4)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--theme-surface-2)' }}>
                <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 600, color: 'var(--theme-tx-primary)' }}>{db.database}</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--theme-tx-secondary)', background: 'var(--theme-surface-4)', padding: '4px 10px', borderRadius: '12px' }}>
                    {db.tables.length} tables
                  </span>
                  <button
                    onClick={() => handleDeleteDb(db.database)}
                    disabled={deletingDb === db.database || isUploading || isCreating}
                    title="Delete Database"
                    style={{
                      background: 'rgba(239,68,68,0.1)',
                      border: '1px solid rgba(239,68,68,0.2)',
                      color: '#ef4444',
                      borderRadius: '8px',
                      padding: '6px 12px',
                      cursor: (deletingDb === db.database || isUploading || isCreating) ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '12px',
                      fontWeight: 600,
                      opacity: (deletingDb === db.database || isUploading || isCreating) ? 0.5 : 1
                    }}
                  >
                    {deletingDb === db.database ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Trash2 size={14} />}
                    Delete
                  </button>
                </div>
              </div>

              <div style={{ padding: '24px', display: 'grid', gridTemplateColumns: '1fr 300px', gap: '32px' }}>
                
                {/* Tables Status */}
                <div>
                  <h3 style={{ fontSize: '14px', color: 'var(--theme-tx-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px', marginTop: 0 }}>Standard Measure Files</h3>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '24px' }}>
                    {STANDARD_TABLES.map(table => {
                      const present = db.tables.includes(table)
                      return (
                        <div key={table} style={{ 
                          display: 'flex', alignItems: 'center', gap: '6px', 
                          padding: '6px 12px', borderRadius: '6px', fontSize: '13px', fontWeight: 500,
                          background: present ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.05)',
                          color: present ? '#34d399' : 'var(--theme-tx-secondary)',
                          border: `1px solid ${present ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.05)'}`
                        }}>
                          {present ? <CheckCircle2 size={14} /> : <XCircle size={14} color="var(--theme-tx-muted)" />}
                          {table}
                        </div>
                      )
                    })}
                  </div>

                  {customTables.length > 0 && (
                    <>
                      <h3 style={{ fontSize: '14px', color: 'var(--theme-tx-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px', marginTop: 0 }}>Custom Tables</h3>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {customTables.map(table => (
                          <div key={table} style={{ 
                            padding: '6px 12px', borderRadius: '6px', fontSize: '13px', fontWeight: 500,
                            background: 'var(--theme-surface-4)', color: '#a78bfa', border: '1px solid var(--theme-border-bright)'
                          }}>
                            {table}
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>

                {/* Upload Zone */}
                <div>
                  <h3 style={{ fontSize: '14px', color: 'var(--theme-tx-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px', marginTop: 0 }}>Append Data</h3>
                  <div 
                    onDragOver={e => e.preventDefault()}
                    onDrop={e => handleAppendDrop(e, db.database)}
                    onClick={() => document.getElementById(`file-input-${db.database}`)?.click()}
                    style={{
                      border: '2px dashed var(--theme-border-bright)',
                      borderRadius: '8px',
                      padding: '32px 16px',
                      textAlign: 'center',
                      cursor: isUploading ? 'not-allowed' : 'pointer',
                      background: 'var(--theme-surface-2)',
                      transition: 'all 0.2s',
                      opacity: isUploading ? 0.5 : 1
                    }}
                    onMouseEnter={e => { if(!isUploading) e.currentTarget.style.borderColor = 'var(--theme-accent)'; e.currentTarget.style.background = 'var(--theme-surface-2)' }}
                    onMouseLeave={e => { if(!isUploading) e.currentTarget.style.borderColor = 'var(--theme-border-bright)'; e.currentTarget.style.background = 'var(--theme-surface-2)' }}
                  >
                    <input 
                      id={`file-input-${db.database}`}
                      type="file" 
                      multiple
                      onChange={e => handleAppendSelect(e, db.database)}
                      style={{ display: 'none' }}
                      disabled={isUploading}
                    />
                    
                    {isUploading ? (
                      <div style={{ color: 'var(--theme-accent)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                        <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
                        <span style={{ fontSize: '14px', fontWeight: 500 }}>Appending data...</span>
                      </div>
                    ) : (
                      <>
                        <Upload size={24} color="var(--theme-tx-muted)" style={{ marginBottom: '12px' }} />
                        <div style={{ fontSize: '14px', color: 'var(--theme-tx-primary)', fontWeight: 500, marginBottom: '4px' }}>
                          Drag files here
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>
                          or click to browse
                        </div>
                        {standardMissing.length > 0 && (
                          <div style={{ marginTop: '12px', fontSize: '11px', color: '#ef4444', background: 'rgba(239,68,68,0.1)', padding: '4px 8px', borderRadius: '4px', display: 'inline-block' }}>
                            Missing: {standardMissing.slice(0, 2).join(', ')} {standardMissing.length > 2 ? `+${standardMissing.length - 2} more` : ''}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  {dbError && (
                    <div style={{ marginTop: '12px', fontSize: '12px', color: '#ef4444' }}>
                      {dbError}
                    </div>
                  )}
                </div>

              </div>
            </div>
          )
        })}

        {details.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: '64px', color: 'var(--theme-tx-secondary)', background: 'var(--theme-surface-1)', borderRadius: '12px', border: '1px dashed var(--theme-border-bright)' }}>
            No databases found. Go to the Upload page to create your first one.
          </div>
        )}
      </div>

    </div>
    </div>
  )
}
