import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'

const TERMINAL_STATUSES = ['completed', 'failed']

export default function Results() {
  const router = useRouter()
  const { note_id } = router.query
  const [status, setStatus] = useState('pending')
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!note_id) return

    const poll = async () => {
      try {
        const res = await fetch(`/api/notes/${note_id}/status`)
        if (!res.ok) {
          setError('Note not found')
          clearInterval(intervalRef.current)
          return
        }
        const data = await res.json()
        setStatus(data.status)

        if (data.status === 'completed') {
          clearInterval(intervalRef.current)
          const resultsRes = await fetch(`/api/notes/${note_id}/results`)
          const resultsData = await resultsRes.json()
          setResults(resultsData.tasks)
        } else if (data.status === 'failed') {
          clearInterval(intervalRef.current)
          setError('Processing failed. Please try uploading again.')
        }
      } catch (err) {
        setError('Connection error')
        clearInterval(intervalRef.current)
      }
    }

    poll()
    intervalRef.current = setInterval(poll, 3000)

    return () => clearInterval(intervalRef.current)
  }, [note_id])

  const isProcessing = !TERMINAL_STATUSES.includes(status)

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-800">Processing Results</h1>
          <Link href="/" className="text-blue-600 text-sm hover:underline">
            Upload another
          </Link>
        </div>

        <p className="text-gray-400 text-xs mb-4">Note ID: {note_id}</p>

        {isProcessing && !error && (
          <div className="bg-white rounded-2xl shadow-md p-8 text-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600 font-medium capitalize">{status}...</p>
            <p className="text-gray-400 text-sm mt-1">Checking every 3 seconds</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-red-600">
            {error}
          </div>
        )}

        {results && (
          <div className="space-y-4">
            <Section title="Lab Tests" items={results.lab_tests} color="blue" />
            <Section title="Radiology" items={results.radiology} color="purple" />
            <Section title="Follow-ups" items={results.followups} color="green" />
          </div>
        )}
      </div>
    </div>
  )
}

function Section({ title, items, color }) {
  const colorMap = {
    blue: 'bg-blue-50 border-blue-200',
    purple: 'bg-purple-50 border-purple-200',
    green: 'bg-green-50 border-green-200',
  }
  return (
    <div className={`rounded-2xl border p-5 ${colorMap[color]}`}>
      <h2 className="font-semibold text-gray-700 mb-3">{title}</h2>
      {!items || items.length === 0 ? (
        <p className="text-gray-400 text-sm">None found</p>
      ) : (
        <ul className="space-y-1">
          {items.map((item, i) => (
            <li key={i} className="text-gray-700 text-sm flex items-start gap-2">
              <span className="mt-1 text-gray-400">•</span>
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
