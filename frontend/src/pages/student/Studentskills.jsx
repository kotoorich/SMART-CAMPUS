import { Sparkles } from "lucide-react";
import { useEffect, useState, useCallback } from "react"
import MainLayout from "../../layouts/MainLayout"
import { getProfile, updateInterests, getRecommendations } from "../../services/api"

const SUGGESTED_TAGS = [
  "AI", "Machine Learning", "Deep Learning", "Computer Vision", "NLP",
  "Data Science", "Python", "Web Development", "React", "Node.js",
  "Full Stack", "Cloud", "AWS", "DevOps", "Docker", "Kubernetes",
  "Cybersecurity", "Ethical Hacking", "Android", "Flutter",
  "IoT", "Blockchain", "SQL", "MongoDB", "Java", "C++",
  "UI/UX", "Figma", "Competitive Programming", "Algorithms",
  "Entrepreneurship", "Digital Marketing", "Product Management",
  "Data Visualisation", "Tableau", "Generative AI", "LLM",
]

const CATEGORY_COLORS = {
  AI:              "bg-purple-100 text-purple-700 border-purple-200",
  Data:            "bg-green-100 text-green-700 border-green-200",
  Web:             "bg-blue-100 text-blue-700 border-blue-200",
  Cloud:           "bg-sky-100 text-sky-700 border-sky-200",
  Security:        "bg-red-100 text-red-700 border-red-200",
  Mobile:          "bg-orange-100 text-orange-700 border-orange-200",
  IoT:             "bg-teal-100 text-teal-700 border-teal-200",
  Database:        "bg-yellow-100 text-yellow-700 border-yellow-200",
  Programming:     "bg-indigo-100 text-indigo-700 border-indigo-200",
  Design:          "bg-pink-100 text-pink-700 border-pink-200",
  Business:        "bg-amber-100 text-amber-700 border-amber-200",
  "Soft Skills":   "bg-lime-100 text-lime-700 border-lime-200",
  Blockchain:      "bg-violet-100 text-violet-700 border-violet-200",
  "Emerging Tech": "bg-cyan-100 text-cyan-700 border-cyan-200",
}

// ── Score a course purely in-memory — NO API calls ────────────────────────────
function scoreCourse(course, interestWords) {
  if (interestWords.size === 0) return 0
  const tagWords   = new Set(course.skill_tag.toLowerCase().replace(/[,-]/g, " ").split(/\s+/).filter(Boolean))
  const titleWords = new Set(course.title.toLowerCase().split(/\s+/).filter(Boolean))
  let s = 0
  interestWords.forEach(iw => {
    if (tagWords.has(iw))   s += 2
    if (titleWords.has(iw)) s += 1
    // partial match bonus
    tagWords.forEach(tw => { if (tw !== iw && (tw.includes(iw) || iw.includes(tw))) s += 1 })
  })
  return s
}

// Parse interests string into a clean Set of lowercase words (length > 2)
function parseInterestWords(raw) {
  return new Set(
    raw.toLowerCase().replace(/,/g, " ").split(/\s+/).filter(w => w.length > 2)
  )
}

// Parse interests string into display tags array (trimmed, non-empty, de-duped)
function parseTags(raw) {
  const seen = new Set()
  return raw.split(",")
    .map(s => s.trim())
    .filter(s => {
      if (!s || seen.has(s.toLowerCase())) return false
      seen.add(s.toLowerCase())
      return true
    })
}

export default function StudentSkills() {
  const [profile,    setProfile]    = useState(null)
  const [interests,  setInterests]  = useState("")
  const [allCourses, setAllCourses] = useState([])   // stored ONCE — never re-fetched on keystroke
  const [preview,    setPreview]    = useState([])
  const [saving,     setSaving]     = useState(false)
  const [saved,      setSaved]      = useState(false)
  const [error,      setError]      = useState("")
  const [loading,    setLoading]    = useState(true)

  // ── Initial load — fetch profile + courses ONCE ──────────────────────────
  useEffect(() => {
    Promise.all([getProfile(), getRecommendations()])
      .then(([prof, courses]) => {
        setProfile(prof)
        const savedInterests = prof.interests || ""
        setInterests(savedInterests)
        setAllCourses(courses)
        // Set initial preview from already-scored backend response
        const initial = [...courses]
          .sort((a, b) => (b.score || 0) - (a.score || 0))
          .slice(0, 6)
        setPreview(initial)
      })
      .catch(() => setError("Could not load profile. Please refresh."))
      .finally(() => setLoading(false))
  }, [])

  // ── Live preview — re-score in-memory whenever interests text changes ─────
  // No API calls here — uses allCourses already in state
  const updatePreview = useCallback((raw) => {
    if (!raw.trim() || allCourses.length === 0) {
      setPreview([])
      return
    }
    const words = parseInterestWords(raw)
    const scored = [...allCourses]
      .map(c => ({ ...c, _localScore: scoreCourse(c, words) }))
      .sort((a, b) => b._localScore - a._localScore)
    setPreview(scored.slice(0, 6))
  }, [allCourses])

  useEffect(() => {
    updatePreview(interests)
  }, [interests, updatePreview])

  // ── Tag helpers ──────────────────────────────────────────────────────────
  const currentTags = parseTags(interests)

  const addTag = (tag) => {
    const existing = parseTags(interests)
    if (!existing.map(s => s.toLowerCase()).includes(tag.toLowerCase())) {
      setInterests(prev => {
        const trimmed = prev.trim()
        return trimmed ? `${trimmed}, ${tag}` : tag
      })
    }
  }

  const removeTag = (tag) => {
    const updated = parseTags(interests).filter(
      s => s.toLowerCase() !== tag.toLowerCase()
    )
    setInterests(updated.join(", "))
  }

  // ── Save ─────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    const clean = interests.trim()
    if (!clean) return setError("Please enter at least one interest before saving.")
    setSaving(true)
    setError("")
    setSaved(false)
    try {
      await updateInterests(clean)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e) {
      setError(e.message || "Failed to save. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  // ── Loading state ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <MainLayout>
        <div className="mt-10 text-center text-gray-400 animate-pulse">Loading profile...</div>
      </MainLayout>
    )
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <MainLayout>
      <div className="mt-6 max-w-4xl">

        <h2 className="page-heading text-2xl font-bold text-gray-800 mb-1"><Sparkles size={23}/> Skills & Interests</h2>
        <p className="text-gray-500 text-sm mb-8">
          Update your interests to get personalised NEP course recommendations.
        </p>

        <div className="grid md:grid-cols-2 gap-6">

          {/* ── LEFT: Edit Panel ─────────────────────────────────────────── */}
          <div className="space-y-5">

            {/* Profile card */}
            <div className="bg-white rounded-2xl shadow-sm border p-5 flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-blue-600 text-white flex items-center justify-center text-xl font-bold shrink-0">
                {profile?.name?.[0]?.toUpperCase() ?? "S"}
              </div>
              <div className="min-w-0">
                <p className="font-semibold text-gray-800 truncate">{profile?.name}</p>
                <p className="text-sm text-gray-400 truncate">{profile?.department} · {profile?.email}</p>
              </div>
            </div>

            {/* Active tags */}
            <div className="bg-white rounded-2xl shadow-sm border p-5">
              <p className="text-sm font-semibold text-gray-700 mb-3">Your Current Interests</p>
              {currentTags.length === 0 ? (
                <p className="text-gray-400 text-sm">No interests added yet. Pick from suggestions below.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {currentTags.map(tag => (
                    <span
                      key={`active-${tag}`}
                      className="flex items-center gap-1 px-3 py-1 bg-blue-50 border border-blue-200 text-blue-700 rounded-full text-sm font-medium"
                    >
                      {tag}
                      <button
                        onClick={() => removeTag(tag)}
                        className="ml-1 text-blue-400 hover:text-red-500 transition text-xs font-bold leading-none"
                        aria-label={`Remove ${tag}`}
                      >
                        
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Free-text textarea */}
            <div className="bg-white rounded-2xl shadow-sm border p-5">
              <label className="text-sm font-semibold text-gray-700 block mb-2">
                Edit Interests (comma-separated)
              </label>
              <textarea
                value={interests}
                onChange={e => { setInterests(e.target.value); setError("") }}
                rows={3}
                placeholder="e.g. Machine Learning, Python, Web Development, Cloud"
                className="w-full border rounded-xl p-3 text-sm outline-none focus:border-blue-400 resize-none transition"
              />
              <p className="text-xs text-gray-400 mt-1">
                Separate interests with commas · or click suggestions below to add/remove
              </p>
            </div>

            {/* Quick-add suggestion chips */}
            <div className="bg-white rounded-2xl shadow-sm border p-5">
              <p className="text-sm font-semibold text-gray-700 mb-3"> Quick Add</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_TAGS.map(tag => {
                  const added = currentTags.map(s => s.toLowerCase()).includes(tag.toLowerCase())
                  return (
                    <button
                      key={`suggest-${tag}`}
                      onClick={() => added ? removeTag(tag) : addTag(tag)}
                      className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                        added
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-gray-50 text-gray-600 border-gray-200 hover:border-blue-400 hover:text-blue-600"
                      }`}
                    >
                      {added ? " " : "+ "}{tag}
                    </button>
                  )
                })}
              </div>
            </div>

            {error && (
              <p className="text-red-500 text-sm bg-red-50 border border-red-200 rounded-xl px-4 py-2">
                {error}
              </p>
            )}

            <button
              onClick={handleSave}
              disabled={saving}
              className={`w-full py-3 rounded-xl font-semibold transition text-white ${
                saving ? "bg-gray-400 cursor-not-allowed"
                : saved  ? "bg-green-600"
                : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {saving ? "Saving..." : saved ? " Saved!" : "Save Interests"}
            </button>

          </div>

          {/* ── RIGHT: Live Preview ──────────────────────────────────────── */}
          <div>
            <div className="bg-white rounded-2xl shadow-sm border p-5 sticky top-6">
              <p className="text-sm font-semibold text-gray-700 mb-1">
                 Live Recommendation Preview
              </p>
              <p className="text-xs text-gray-400 mb-4">
                Updates as you change your interests · no save needed to preview
              </p>

              {preview.length === 0 ? (
                <div className="text-center py-10 text-gray-400">
                  <p className="text-3xl mb-2"></p>
                  <p className="text-sm">Add interests to see matched courses</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {preview.map((course, i) => {
                    const localScore = course._localScore ?? course.score ?? 0
                    const colorClass = CATEGORY_COLORS[course.category] || "bg-gray-100 text-gray-700 border-gray-200"
                    return (
                      <div
                        key={`preview-${course.id}`}
                        className="flex items-start gap-3 p-3 rounded-xl border hover:shadow-sm transition"
                      >
                        <span className="text-gray-300 font-bold text-sm w-5 shrink-0 mt-0.5">
                          {i + 1}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-gray-800 leading-snug line-clamp-2">
                            {course.title}
                          </p>
                          <p className="text-xs text-gray-400 mt-0.5">⏱ {course.duration}</p>
                        </div>
                        <div className="shrink-0 flex flex-col items-end gap-1">
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${colorClass}`}>
                            {course.category}
                          </span>
                          {localScore > 0 && (
                            <span className="text-xs text-green-600 font-semibold">
                              +{localScore}
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  })}
                  <p className="text-xs text-center text-gray-400 pt-1">
                    Save to apply · See all in Courses for you
                  </p>
                </div>
              )}
            </div>
          </div>

        </div>
      </div>
    </MainLayout>
  )
}