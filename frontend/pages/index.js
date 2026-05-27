import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'

function decodeName(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.name || payload.email || ''
  } catch {
    return ''
  }
}

export default function Home() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [userName, setUserName] = useState('')
  const router = useRouter()

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/login')
    } else {
      setUserName(decodeName(token))
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('token')
    router.push('/login')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) return

    setLoading(true)
    setError('')

    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/login')
      return
    }

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/notes/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      if (res.status === 401) {
        localStorage.removeItem('token')
        router.push('/login')
        return
      }

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Upload failed')
      }

      const data = await res.json()
      router.push(`/results/${data.note_id}`)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top navbar */}
      <nav className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <span className="text-lg font-bold text-blue-600">DocsProcessor</span>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">{userName}</span>
          <button
            onClick={handleLogout}
            className="text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-lg transition"
          >
            Sign out
          </button>
        </div>
      </nav>

      {/* Main content */}
      <div className="flex items-center justify-center p-4 mt-16">
        <div className="bg-white rounded-2xl shadow-md p-8 w-full max-w-md">
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Upload Medical Note</h1>
          <p className="text-gray-500 text-sm mb-6">
            Upload a prescription or medical note to extract lab tests, radiology orders, and follow-ups.
            Supported formats: .txt, .pdf, .jpg, .png
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400 transition">
              <input
                type="file"
                accept=".txt,.pdf,.png,.jpg,.jpeg"
                onChange={(e) => setFile(e.target.files[0])}
                className="hidden"
              />
              {file ? (
                <div>
                  <p className="text-gray-700 font-medium">{file.name}</p>
                  <p className="text-gray-400 text-xs mt-1">{(file.size / 1024).toFixed(1)} KB</p>
                </div>
              ) : (
                <div>
                  <p className="text-gray-400 text-sm">Click to select a file</p>
                  <p className="text-gray-300 text-xs mt-1">.txt · .pdf · .jpg · .png (max 10 MB)</p>
                </div>
              )}
            </label>

            {error && (
              <p className="text-red-500 text-sm">{error}</p>
            )}

            <button
              type="submit"
              disabled={!file || loading}
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {loading ? 'Uploading...' : 'Upload & Process'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
