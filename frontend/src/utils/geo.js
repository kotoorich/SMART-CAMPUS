// Shared high-accuracy location helper for the attendance workflow.
//
// Browsers commonly return a coarse first fix before refining it, and indoor
// fixes can be tens of metres off. Sampling fixes for a short window and
// keeping the most accurate one gives attendance a far more trustworthy
// anchor than a single getCurrentPosition call.
//
// Desktop browsers and laptops without a real GPS chip often cannot satisfy a
// high-accuracy request at all (they report POSITION_UNAVAILABLE or time out).
// When that happens we retry with enableHighAccuracy:false so a coarse
// network-derived fix is still usable — the backend records the accuracy as
// evidence and judges proximity by distance rather than blocking outright.

const GOOD_ACCURACY_METERS = 20;

function sample({ enableHighAccuracy, sampleMs, timeoutMs }) {
  return new Promise((resolve, reject) => {
    let best = null;
    let done = false;
    let watchId = null;
    let timer = null;
    const finish = (err) => {
      if (done) return;
      done = true;
      if (watchId != null) navigator.geolocation.clearWatch(watchId);
      if (timer != null) clearTimeout(timer);
      if (best) resolve(best);
      else reject(err);
    };
    const onFix = (p) => {
      const fix = { latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy: p.coords.accuracy };
      if (!best || fix.accuracy < best.accuracy) best = fix;
      if (fix.accuracy <= GOOD_ACCURACY_METERS) finish();
    };
    const onError = (e) => {
      // A single transient error should not abort the sample window while we
      // already have a usable fix; only give up when nothing arrived.
      if (best) return;
      finish(Object.assign(new Error("geolocation"), { code: e.code }));
    };
    watchId = navigator.geolocation.watchPosition(onFix, onError, {
      enableHighAccuracy, maximumAge: 0, timeout: timeoutMs,
    });
    timer = setTimeout(() => finish(), sampleMs);
  });
}

export async function getBestPosition() {
  if (!navigator.geolocation) {
    throw new Error("This device or browser does not support location services, which are required for attendance.");
  }
  try {
    return await sample({ enableHighAccuracy: true, sampleMs: 12000, timeoutMs: 25000 });
  } catch (err) {
    if (err?.code === 1) {
      throw new Error("Location permission was denied. Enable precise location in your browser settings and try again.");
    }
    // High-accuracy fix unavailable (common on laptops without a GPS chip):
    // fall back to a standard-accuracy request before giving up.
    try {
      return await sample({ enableHighAccuracy: false, sampleMs: 10000, timeoutMs: 20000 });
    } catch (err2) {
      if (err2?.code === 1) {
        throw new Error("Location permission was denied. Enable precise location in your browser settings and try again.");
      }
      throw new Error("We could not obtain your current location. Turn on GPS/location services and retry.");
    }
  }
}
