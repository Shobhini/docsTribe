import { useState } from 'react'
import { useRouter } from 'next/router'

export default function Home() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) return

    setLoading(true)
    setError('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/notes/upload', {
        method: 'POST',
        body: formData,
      })

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
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-md p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-gray-800 mb-2">Medical Notes Processor</h1>
        <p className="text-gray-500 text-sm mb-6">
          Upload a prescription or medical note to extract lab tests, radiology orders, and follow-ups.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block border-2 border-dashed border-gray-300 rounded-xl p-6 text-center cursor-pointer hover:border-blue-400 transition">
            <input
              type="file"
              accept=".txt,.pdf,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files[0])}
              className="hidden"
            />
            {file ? (
              <span className="text-gray-700 font-medium">{file.name}</span>
            ) : (
              <span className="text-gray-400">Click to select a file (.txt, .pdf, .jpg, .png)</span>
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
  )
}
