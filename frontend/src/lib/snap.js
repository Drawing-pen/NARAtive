let pending = null

export function loadSnap(src, clientKey) {
  if (window.snap) return Promise.resolve(window.snap)
  if (pending) return pending
  pending = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = src
    script.setAttribute('data-client-key', clientKey)
    script.async = true
    const fail = () => {
      pending = null
      script.remove()
      reject(new Error('Skrip pembayaran gagal dimuat.'))
    }
    script.onload = () => (window.snap ? resolve(window.snap) : fail())
    script.onerror = fail
    document.head.appendChild(script)
  })
  return pending
}
