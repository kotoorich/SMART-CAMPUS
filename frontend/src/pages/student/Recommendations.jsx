import { BookOpen } from "lucide-react";
import { useEffect, useState, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import MainLayout from "../../layouts/MainLayout"
import { getRecommendations } from "../../services/api"

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

const CATEGORY_ICONS = {
  AI: "", Data: "", Web: "", Cloud: "", Security: "",
  Mobile: "", IoT: "", Database: "", Programming: "",
  Design: "", Business: "", "Soft Skills": "",
  Blockchain: "", "Emerging Tech": "",
}

// Fixed category order so tabs don't shuffle when courses filter
const FIXED_CATEGORY_ORDER = [
  "AI", "Data", "Web", "Cloud", "Security", "Mobile", "IoT",
  "Database", "Programming", "Design", "Business", "Soft Skills",
  "Blockchain", "Emerging Tech",
]

export default function Recommendations() {
  const navigate = useNavigate()
  const [courses,        setCourses]        = useState([])
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState("")
  const [search,         setSearch]         = useState("")
  const [activeCategory, setActiveCategory] = useState("All")

  // ── Fetch courses once on mount ──────────────────────────────────────────
  useEffect(() => {
    getRecommendations()
      .then(data => setCourses(data))
      .catch(err  => setError(err.message || "Could not load recommendations"))
      .finally(()  => setLoading(false))
  }, [])

    // Filtered catalogue derived directly from state — no effect required.
  const filtered = useMemo(() => {
    let result = [...courses]

    if (activeCategory !== "All") {
      result = result.filter(c => c.category === activeCategory)
    }

    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(c =>
        c.title.toLowerCase().includes(q) ||
        c.skill_tag.toLowerCase().includes(q) ||
        (c.platform    || "").toLowerCase().includes(q) ||
        (c.description || "").toLowerCase().includes(q)
      )
    }

    return result
  }, [search, activeCategory, courses])

  // Only show categories that actually exist in loaded courses
  const presentCategories = FIXED_CATEGORY_ORDER.filter(cat =>
    courses.some(c => c.category === cat)
  )
  const categories = ["All", ...presentCategories]

  const matchCount   = courses.filter(c => (c.score || 0) > 0).length
  const hasInterests = matchCount > 0

  return (
    <MainLayout>
      <div className="mt-6">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="page-heading text-2xl font-bold text-gray-800"><BookOpen size={23}/> Courses for you</h2>
            <p className="text-gray-500 text-sm mt-1">
              {hasInterests
                ? `${matchCount} courses matched to your interests · sorted by relevance`
                : "Showing all programs · set your interests for personalised matches"}
            </p>
          </div>
          <button
            onClick={() => navigate("/student/skills")}
            className="text-sm text-blue-600 hover:underline font-medium flex items-center gap-1 mt-1 shrink-0 ml-4"
          >
             Edit Interests
          </button>
        </div>

        {/* ── No-interests nudge banner ───────────────────────────────────── */}
        {!hasInterests && !loading && (
          <div className="mb-5 bg-blue-50 border border-blue-200 rounded-2xl p-4 flex items-center gap-3">
            <span className="text-2xl shrink-0"></span>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-blue-800 text-sm">Get personalised recommendations</p>
              <p className="text-blue-600 text-xs mt-0.5">
                Set your skills & interests to see courses ranked by relevance
              </p>
            </div>
            <button
              onClick={() => navigate("/student/skills")}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-xl hover:bg-blue-700 transition font-medium shrink-0"
            >
              Set Interests
            </button>
          </div>
        )}

        {/* ── Search bar ──────────────────────────────────────────────────── */}
        <div className="mb-4">
          <input
            type="text"
            placeholder=" Search courses, skills, platforms..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full border rounded-xl px-4 py-2.5 text-sm outline-none focus:border-blue-400 transition bg-white"
          />
        </div>

        {/* ── Category filter tabs ─────────────────────────────────────────── */}
        <div className="flex flex-wrap gap-2 mb-5">
          {categories.map(cat => (
            <button
              key={`cat-${cat}`}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition ${
                activeCategory === cat
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-600 border-gray-200 hover:border-blue-400"
              }`}
            >
              {cat !== "All" && (CATEGORY_ICONS[cat] ?? "")} {cat}
              {cat !== "All" && (
                <span className="ml-1 opacity-60">
                  ({courses.filter(c => c.category === cat).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Skeleton loaders ─────────────────────────────────────────────── */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={`skeleton-${i}`} className="bg-white rounded-2xl shadow-sm border p-5 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
                <div className="h-3 bg-gray-100 rounded w-1/2 mb-2" />
                <div className="h-3 bg-gray-100 rounded w-full" />
              </div>
            ))}
          </div>
        )}

        {/* ── Error ───────────────────────────────────────────────────────── */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-600 text-sm">
            {error}
          </div>
        )}

        {/* ── Empty state ──────────────────────────────────────────────────── */}
        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-4xl mb-3"></p>
            <p className="font-medium">No courses found</p>
            <p className="text-sm mt-1">Try a different search term or category</p>
            {(search || activeCategory !== "All") && (
              <button
                onClick={() => { setSearch(""); setActiveCategory("All") }}
                className="mt-4 text-sm text-blue-600 hover:underline"
              >
                Clear filters
              </button>
            )}
          </div>
        )}

        {/* ── Course Grid ──────────────────────────────────────────────────── */}
        {!loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((course) => {
              const colorClass = CATEGORY_COLORS[course.category] || "bg-gray-100 text-gray-700 border-gray-200"
              const icon       = CATEGORY_ICONS[course.category]  || ""
              const isMatch    = (course.score || 0) > 0

              // De-dupe skill tags before rendering chips to prevent duplicate React keys
              const skillChips = [...new Set(
                course.skill_tag.split(/\s+/).map(t => t.trim()).filter(t => t.length > 2)
              )].slice(0, 5)

              return (
                <div
                  key={`course-${course.id}`}
                  className={`bg-white rounded-2xl border p-5 hover:shadow-md transition flex flex-col gap-3 ${
                    isMatch ? "border-blue-100 shadow-sm" : "border-gray-100"
                  }`}
                >
                  {/* Title + Category badge */}
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold text-gray-800 leading-snug flex-1">
                      {icon} {course.title}
                    </h3>
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium shrink-0 ${colorClass}`}>
                      {course.category}
                    </span>
                  </div>

                  {/* Description */}
                  {course.description && (
                    <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">
                      {course.description}
                    </p>
                  )}

                  {/* Skill chips — de-duped, index-keyed to avoid duplicates */}
                  {skillChips.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {skillChips.map((tag, idx) => (
                        <span
                          key={`chip-${course.id}-${idx}`}
                          className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full capitalize"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Footer: duration + platform + match badge */}
                  <div className="flex items-center justify-between mt-auto pt-2 border-t border-gray-50">
                    <div className="text-xs text-gray-400 space-y-0.5">
                      <p>⏱ {course.duration}</p>
                      {course.platform && <p> {course.platform}</p>}
                    </div>
                    {isMatch && (
                      <span className="text-xs text-green-600 font-semibold bg-green-50 px-2 py-0.5 rounded-full border border-green-100">
                         Matched
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <p className="text-xs text-center text-gray-400 mt-8">
          {filtered.length} of {courses.length} programs · NEP 2020 aligned skill-enhancement courses
        </p>

      </div>
    </MainLayout>
  )
}