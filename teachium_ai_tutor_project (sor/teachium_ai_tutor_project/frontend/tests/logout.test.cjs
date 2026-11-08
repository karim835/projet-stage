const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { transformSync } = require('esbuild')

// Exercise the real provider callbacks with controlled delayed HTTP responses.
function harness() {
  const states = []
  const effects = []
  const refs = []
  const routes = []
  let cursor = 0
  let refCursor = 0
  let token = 'existing-session'
  let resolveRequest
  const pending = new Promise((resolve) => { resolveRequest = resolve })
  const react = {
    createContext: () => ({ Provider: 'Provider' }),
    createElement: (_type, props) => props,
    useState(initial) {
      const i = cursor++
      if (!(i in states)) states[i] = initial
      return [states[i], (value) => { states[i] = value }]
    },
    useRef(initial) {
      const i = refCursor++
      return refs[i] ||= { current: initial }
    },
    useCallback: (fn) => fn,
    useMemo: (fn) => fn(),
    useEffect: (fn) => effects.push(fn),
    useContext: () => null,
  }
  const apiModule = {
    authApi: { me: () => pending, login: () => pending, register: () => pending },
    api: { interceptors: { response: { use: () => 1, eject() {} } } },
    getToken: () => token,
    setToken: (value) => { token = value },
    readError: () => 'Request failed',
  }
  const source = fs.readFileSync(path.join(__dirname, '../src/context/AuthContext.jsx'), 'utf8')
  const code = transformSync(source, { loader: 'jsx', format: 'cjs', jsx: 'transform', jsxFactory: 'React.createElement' }).code
  const module = { exports: {} }
  vm.runInNewContext(code, {
    module, exports: module.exports, React: react,
    require(name) {
      if (name === 'react') return react
      if (name === 'react-router-dom') return { useNavigate: () => (url, options) => routes.push({ url, replace: options.replace }) }
      return apiModule
    },
  })
  function render() {
    cursor = 0
    refCursor = 0
    return module.exports.AuthProvider({ children: null }).value
  }
  return { render, effects, routes, resolve: (data) => resolveRequest({ data }), token: () => token }
}

test('sign-out clears the token and redirects even with session restoration pending', async () => {
  const h = harness()
  const auth = h.render()
  h.effects[1]()
  auth.logout()
  assert.equal(h.token(), null)
  assert.deepEqual(h.routes, [{ url: '/connexion', replace: true }])
  h.resolve({ id: 1, role: 'learner' })
  await new Promise(setImmediate)
  assert.equal(h.render().user, null)
  assert.equal(h.render().loading, false)
})

test('a pending login cannot sign the user back in after logout', async () => {
  const h = harness()
  const auth = h.render()
  const login = auth.login('demo@example.test', 'password')
  auth.logout()
  h.resolve({ access_token: 'late-token', user: { id: 2, role: 'trainer' } })
  assert.equal((await login).ok, false)
  assert.equal(h.token(), null)
  assert.equal(h.render().user, null)
})
