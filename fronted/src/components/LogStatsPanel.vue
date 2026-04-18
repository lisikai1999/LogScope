<template>
  <div class="stats-panel">
    <div class="stats-header" @click="togglePanel">
      <span class="stats-title">
        <span class="icon">📊</span>
        日志统计
      </span>
      <span class="toggle-icon">{{ isExpanded ? '▼' : '▶' }}</span>
    </div>
    
    <transition name="collapse">
      <div v-if="isExpanded" class="stats-content">
        <div class="stats-grid">
          <div class="stats-card">
            <h3>日志级别分布</h3>
            <div class="level-distribution">
              <div 
                v-for="(count, level) in levelStats" 
                :key="level" 
                class="level-item"
                :class="`level-${level.toLowerCase()}`"
              >
                <span class="level-name">{{ level }}</span>
                <span class="level-count">{{ count }}</span>
                <div class="level-bar">
                  <div 
                    class="level-bar-fill" 
                    :style="{ width: `${getLevelPercentage(level)}%` }"
                  ></div>
                </div>
              </div>
            </div>
            <div class="summary-text">
              共 <strong>{{ totalLogs }}</strong> 条日志
              <span v-if="errorRate > 0" class="error-rate">
                | 错误率: <strong :class="errorRate > 10 ? 'high' : ''">{{ errorRate.toFixed(2) }}%</strong>
              </span>
            </div>
          </div>
          
          <div class="stats-card">
            <h3>错误率趋势 (最近10个时间点)</h3>
            <div class="chart-container" ref="trendChartRef"></div>
          </div>
          
          <div class="stats-card stats-card-full">
            <h3>高频关键词 Top 10</h3>
            <div v-if="topKeywords.length > 0" class="keywords-container">
              <div 
                v-for="(keyword, index) in topKeywords" 
                :key="keyword.word"
                class="keyword-item"
                :class="`rank-${index + 1}`"
              >
                <span class="keyword-rank">{{ index + 1 }}</span>
                <span class="keyword-word">{{ keyword.word }}</span>
                <span class="keyword-count">{{ keyword.count }}</span>
                <div class="keyword-bar">
                  <div 
                    class="keyword-bar-fill" 
                    :style="{ width: `${getKeywordPercentage(keyword.count)}%` }"
                  ></div>
                </div>
              </div>
            </div>
            <div v-else class="no-keywords">
              暂无关键词数据
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import {
  Chart,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

Chart.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const props = defineProps({
  logs: {
    type: Array,
    default: () => []
  }
})

const isExpanded = ref(true)
const trendChartRef = ref(null)
let trendChart = null

const levelStats = computed(() => {
  const stats = {
    ERROR: 0,
    WARN: 0,
    INFO: 0,
    DEBUG: 0,
    UNKNOWN: 0
  }
  
  props.logs.forEach(log => {
    const level = detectLogLevel(log.message)
    if (stats[level] !== undefined) {
      stats[level]++
    } else {
      stats.UNKNOWN++
    }
  })
  
  return stats
})

const totalLogs = computed(() => {
  return Object.values(levelStats.value).reduce((sum, count) => sum + count, 0)
})

const errorRate = computed(() => {
  if (totalLogs.value === 0) return 0
  return ((levelStats.value.ERROR + levelStats.value.WARN) / totalLogs.value) * 100
})

const topKeywords = computed(() => {
  if (props.logs.length === 0) return []
  
  const wordCounts = {}
  const stopWords = new Set([
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
    'through', 'during', 'before', 'after', 'above', 'below', 'between',
    'and', 'but', 'or', 'so', 'if', 'then', 'else', 'when', 'what', 'which',
    'this', 'that', 'these', 'those', 'it', 'its', 'he', 'she', 'they', 'we',
    'you', 'i', 'me', 'him', 'her', 'them', 'my', 'your', 'his', 'our', 'their',
    'has', 'have', 'had', 'will', 'would', 'could', 'should', 'may', 'might',
    'can', 'shall', 'must', 'ought', 'used', 'get', 'got', 'getting', 'make',
    'made', 'making', 'do', 'does', 'did', 'doing', 'say', 'said', 'saying',
    'go', 'went', 'going', 'come', 'came', 'coming', 'take', 'took', 'taking',
    'see', 'saw', 'seeing', 'know', 'knew', 'knowing', 'think', 'thought',
    'want', 'wanted', 'wanting', 'use', 'using', 'find', 'found', 'finding',
    'give', 'gave', 'giving', 'tell', 'told', 'telling', 'work', 'worked',
    'call', 'called', 'try', 'tried', 'trying', 'ask', 'asked', 'asking',
    'need', 'needed', 'needing', 'feel', 'felt', 'feeling', 'become', 'became',
    'leave', 'left', 'put', 'keep', 'kept', 'let', 'begin', 'began', 'show',
    'showed', 'hear', 'heard', 'play', 'played', 'run', 'ran', 'move', 'moved',
    'live', 'lived', 'believe', 'believed', 'bring', 'brought', 'happen',
    'happened', 'write', 'wrote', 'provide', 'provided', 'sit', 'sat', 'stand',
    'stood', 'lose', 'lost', 'pay', 'paid', 'meet', 'met', 'include', 'included',
    'continue', 'continued', 'set', 'learn', 'learned', 'change', 'changed',
    'lead', 'led', 'understand', 'understood', 'watch', 'watched', 'follow',
    'followed', 'stop', 'stopped', 'create', 'created', 'speak', 'spoke',
    'read', 'spend', 'spent', 'grow', 'grew', 'open', 'opened', 'walk', 'walked',
    'win', 'won', 'offer', 'offered', 'remember', 'remembered', 'love', 'loved',
    'consider', 'considered', 'appear', 'appeared', 'buy', 'bought', 'wait',
    'waited', 'serve', 'served', 'die', 'died', 'send', 'sent', 'expect',
    'expected', 'build', 'built', 'stay', 'stayed', 'fall', 'fell', 'cut',
    'reach', 'reached', 'kill', 'killed', 'remain', 'remained', 'suggest',
    'suggested', 'raise', 'raised', 'pass', 'passed', 'sell', 'sold', 'require',
    'required', 'report', 'reported', 'decide', 'decided', 'pull', 'pulled',
    'allow', 'allowed', 'add', 'added', 'accept', 'accepted', 'answer', 'answered',
    'carry', 'carried', 'drive', 'drove', 'draw', 'drew', 'explain', 'explained',
    'hope', 'hoped', 'pick', 'picked', 'turn', 'turned', 'realize', 'realized',
    'deliver', 'delivered', 'hold', 'held', 'maintain', 'maintained', 'mean',
    'meant', 'fill', 'filled', 'visit', 'visited', 'treat', 'treated', 'catch',
    'caught', 'draw', 'drew', 'drop', 'dropped', 'produce', 'produced', 'eat',
    'ate', 'cover', 'covered', 'catch', 'caught', 'choose', 'chose', 'cause',
    'caused', 'point', 'pointed', 'listen', 'listened', 'agree', 'agreed', 'enter',
    'entered', 'support', 'supported', 'force', 'forced', 'understand', 'understood',
    'very', 'too', 'so', 'just', 'only', 'up', 'out', 'no', 'not', 'now', 'here',
    'there', 'back', 'still', 'even', 'also', 'well', 'again', 'once', 'never',
    'always', 'ever', 'already', 'yet', 'still', 'often', 'sometimes', 'usually',
    'today', 'tomorrow', 'yesterday', 'week', 'month', 'year', 'day', 'hour',
    'minute', 'second', 'time', 'times', 'first', 'last', 'next', 'previous',
    'same', 'different', 'much', 'many', 'more', 'most', 'less', 'least', 'few',
    'fewer', 'fewest', 'other', 'another', 'each', 'every', 'all', 'both', 'either',
    'neither', 'any', 'some', 'such', 'own', 'several', 'enough', 'almost', 'already',
    'actually', 'probably', 'maybe', 'perhaps', 'certainly', 'definitely', 'obviously',
    'however', 'therefore', 'thus', 'hence', 'moreover', 'furthermore', 'additionally',
    'nevertheless', 'nonetheless', 'despite', 'although', 'though', 'even though',
    'while', 'whereas', 'since', 'because', 'unless', 'until', 'whenever', 'wherever',
    'however', 'whatever', 'whoever', 'whichever', 'whomever', 'whose', 'why', 'how',
    'error', 'warning', 'info', 'debug', 'trace', 'fatal', 'log', 'logger', 'logging',
    'request', 'response', 'server', 'client', 'api', 'http', 'https', 'url', 'uri',
    'method', 'get', 'post', 'put', 'delete', 'patch', 'status', 'code', '200', '404',
    '500', '201', '204', '301', '302', '400', '401', '403', '409', '422', '502',
    '503', 'success', 'failed', 'failure', 'successfully', 'unable', 'failed', 'error',
    'exception', 'throw', 'thrown', 'catch', 'caught', 'finally', 'try', 'except',
    'null', 'undefined', 'nan', 'true', 'false', 'none', 'nil', 'void', 'empty',
    'string', 'int', 'integer', 'float', 'double', 'long', 'short', 'byte', 'char',
    'boolean', 'bool', 'array', 'list', 'map', 'dict', 'dictionary', 'object', 'class',
    'interface', 'struct', 'enum', 'function', 'method', 'property', 'attribute', 'field',
    'variable', 'const', 'constant', 'static', 'public', 'private', 'protected', 'final',
    'abstract', 'interface', 'extends', 'implements', 'override', 'overload', 'return',
    'params', 'args', 'arguments', 'parameters', 'type', 'instance', 'new', 'this', 'self',
    'super', 'base', 'prototype', 'constructor', 'destructor', 'init', 'initialize',
    'start', 'stop', 'begin', 'end', 'terminate', 'shutdown', 'restart', 'reload', 'refresh',
    'update', 'delete', 'remove', 'add', 'insert', 'append', 'prepend', 'replace', 'modify',
    'create', 'destroy', 'cleanup', 'dispose', 'free', 'release', 'acquire', 'lock', 'unlock',
    'connect', 'disconnect', 'open', 'close', 'read', 'write', 'send', 'receive', 'fetch',
    'download', 'upload', 'import', 'export', 'load', 'save', 'store', 'cache', 'flush',
    'commit', 'rollback', 'transaction', 'query', 'select', 'insert', 'update', 'delete',
    'where', 'from', 'join', 'inner', 'outer', 'left', 'right', 'group', 'order', 'having',
    'limit', 'offset', 'asc', 'desc', 'and', 'or', 'not', 'in', 'like', 'between', 'is',
    'null', 'true', 'false', 'exists', 'distinct', 'count', 'sum', 'avg', 'min', 'max',
    'having', 'union', 'all', 'as', 'into', 'values', 'set', 'table', 'column', 'row',
    'database', 'db', 'sql', 'mysql', 'postgres', 'mongodb', 'redis', 'elasticsearch',
    'sqlite', 'oracle', 'mssql', 'index', 'primary', 'key', 'foreign', 'constraint',
    'unique', 'default', 'auto_increment', 'identity', 'sequence', 'trigger', 'procedure',
    'function', 'view', 'schema', 'grant', 'revoke', 'backup', 'restore', 'migrate',
    'migration', 'seed', 'seeder', 'factory', 'model', 'controller', 'view', 'router',
    'route', 'middleware', 'filter', 'validator', 'validation', 'authenticate', 'auth',
    'authorization', 'permission', 'role', 'user', 'admin', 'guest', 'anonymous', 'token',
    'jwt', 'oauth', 'session', 'cookie', 'csrf', 'cors', 'xss', 'sql', 'injection', 'attack',
    'security', 'safe', 'unsafe', 'validate', 'sanitize', 'escape', 'encode', 'decode',
    'encrypt', 'decrypt', 'hash', 'salt', 'password', 'secret', 'private', 'public', 'key',
    'certificate', 'ssl', 'tls', 'https', 'secure', 'insecure', 'trust', 'verify', 'sign',
    'signature', 'digest', 'algorithm', 'md5', 'sha1', 'sha256', 'sha512', 'bcrypt', 'argon2',
    'config', 'configuration', 'setting', 'option', 'parameter', 'env', 'environment', 'dotenv',
    'ini', 'json', 'yaml', 'yml', 'xml', 'toml', 'properties', 'conf', 'cfg', 'ini', 'json',
    'development', 'dev', 'production', 'prod', 'staging', 'test', 'testing', 'local', 'remote',
    'debug', 'release', 'verbose', 'quiet', 'silent', 'mode', 'profile', 'build', 'compile',
    'deploy', 'deployment', 'release', 'version', 'tag', 'branch', 'commit', 'merge', 'rebase',
    'pull', 'push', 'fetch', 'clone', 'checkout', 'reset', 'revert', 'stash', 'pop', 'apply',
    'diff', 'log', 'status', 'init', 'add', 'remove', 'rm', 'mv', 'move', 'copy', 'cp',
    'directory', 'folder', 'file', 'path', 'absolute', 'relative', 'root', 'parent', 'child',
    'subdirectory', 'symlink', 'link', 'hard', 'soft', 'permission', 'chmod', 'chown', 'chgrp',
    'owner', 'group', 'read', 'write', 'execute', 'rwx', 'uid', 'gid', 'pid', 'process', 'thread',
    'task', 'job', 'worker', 'pool', 'queue', 'async', 'await', 'callback', 'promise', 'future',
    'coroutine', 'generator', 'yield', 'sleep', 'wait', 'timeout', 'interval', 'delay', 'retry',
    'backoff', 'exponential', 'linear', 'constant', 'jitter', 'circuit', 'breaker', 'retry',
    'fallback', 'graceful', 'degradation', 'timeout', 'cancel', 'abort', 'interrupt', 'signal',
    'kill', 'term', 'int', 'hup', 'quit', 'stop', 'cont', 'usr1', 'usr2', 'daemon', 'service',
    'systemd', 'init', 'upstart', 'supervisor', 'cron', 'scheduled', 'task', 'job', 'batch',
    'queue', 'worker', 'consumer', 'producer', 'broker', 'exchange', 'topic', 'queue', 'routing',
    'key', 'publish', 'subscribe', 'consume', 'produce', 'ack', 'nack', 'reject', 'prefetch',
    'dead', 'letter', 'dlq', 'retry', 'ttl', 'expire', 'persistent', 'durable', 'transient',
    'exclusive', 'auto_delete', 'mandatory', 'immediate', 'priority', 'delivery', 'mode',
    'correlation', 'id', 'reply', 'to', 'headers', 'properties', 'timestamp', 'app', 'id',
    'cluster', 'node', 'replica', 'master', 'slave', 'sentinel', 'proxy', 'load', 'balancer',
    'reverse', 'forward', 'gateway', 'firewall', 'nat', 'route', 'dns', 'hostname', 'ip', 'address',
    'port', 'socket', 'tcp', 'udp', 'http', 'https', 'ftp', 'sftp', 'ssh', 'telnet', 'smtp',
    'pop3', 'imap', 'ldap', 'mysql', 'postgres', 'redis', 'mongodb', 'elasticsearch', 'kafka',
    'rabbitmq', 'activemq', 'zeromq', 'grpc', 'rest', 'soap', 'graphql', 'rpc', 'json', 'xml',
    'yaml', 'yml', 'toml', 'ini', 'csv', 'tsv', 'parquet', 'avro', 'protobuf', 'thrift',
    'compression', 'gzip', 'deflate', 'br', 'snappy', 'lz4', 'zstd', 'archive', 'zip', 'tar',
    'gz', 'bz2', '7z', 'rar', 'extract', 'compress', 'decompress', 'unzip', 'untar',
    'encoding', 'utf-8', 'utf8', 'ascii', 'latin1', 'iso-8859-1', 'unicode', 'base64', 'hex',
    'url', 'encode', 'decode', 'escape', 'unescape', 'quoted', 'printable', 'entity', 'html',
    'javascript', 'css', 'script', 'style', 'link', 'img', 'a', 'href', 'src', 'alt', 'title',
    'class', 'id', 'data', 'aria', 'role', 'type', 'name', 'value', 'placeholder', 'disabled',
    'readonly', 'required', 'checked', 'selected', 'multiple', 'form', 'action', 'method', 'enctype',
    'target', 'submit', 'reset', 'button', 'input', 'textarea', 'select', 'option', 'optgroup',
    'fieldset', 'legend', 'label', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'caption',
    'colgroup', 'col', 'div', 'span', 'p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'pre', 'code', 'samp', 'var', 'kbd', 'mark', 'del', 'ins',
    'sub', 'sup', 'small', 'strong', 'em', 'i', 'b', 'u', 's', 'strike', 'q', 'blockquote', 'cite',
    'abbr', 'acronym', 'dfn', 'time', 'data', 'progress', 'meter', 'details', 'summary', 'dialog',
    'menu', 'menuitem', 'command', 'canvas', 'svg', 'audio', 'video', 'source', 'track', 'embed',
    'object', 'param', 'iframe', 'noscript', 'template', 'slot', 'shadow', 'slot', 'part', 'is',
    'contenteditable', 'draggable', 'spellcheck', 'translate', 'hidden', 'dir', 'lang', 'xml:lang',
    'accesskey', 'tabindex', 'title', 'style', 'class', 'id', 'name', 'data-*', 'aria-*', 'role',
    'react', 'vue', 'angular', 'svelte', 'preact', 'solid', 'lit', 'stencil', 'ember', 'backbone',
    'jquery', 'lodash', 'underscore', 'ramda', 'rxjs', 'moment', 'date-fns', 'luxon', 'dayjs',
    'axios', 'fetch', 'superagent', 'request', 'http', 'https', 'ws', 'socket.io', 'engine.io',
    'express', 'koa', 'hapi', 'nest', 'fastify', 'micro', 'polka', 'restify', 'sails', 'loopback',
    'adonis', 'feathers', 'strapi', 'keystone', 'payload', 'directus', 'pocketbase', 'supabase',
    'firebase', 'amplify', 'vercel', 'netlify', 'cloudflare', 'heroku', 'digitalocean', 'linode',
    'aws', 'azure', 'gcp', 'ibm', 'oracle', 'alibaba', 'tencent', 'baidu', 'serverless', 'lambda',
    'function', 'edge', 'worker', 'container', 'docker', 'podman', 'containerd', 'cri-o', 'rkt',
    'lxc', 'lxd', 'kubernetes', 'k8s', 'openshift', 'rancher', 'istio', 'linkerd', 'envoy', 'nginx',
    'apache', 'caddy', 'traefik', 'haproxy', 'varnish', 'squid', 'nginx', 'apache', 'iis', 'lighttpd',
    'tomcat', 'jetty', 'wildfly', 'glassfish', 'jboss', 'weblogic', 'websphere', 'node', 'deno', 'bun',
    'python', 'pip', 'conda', 'poetry', 'pipenv', 'virtualenv', 'venv', 'pyenv', 'pipx', 'python3',
    'javascript', 'typescript', 'ts', 'js', 'es6', 'es2015', 'es2016', 'es2017', 'es2018', 'es2019',
    'es2020', 'es2021', 'es2022', 'es2023', 'commonjs', 'cjs', 'esm', 'module', 'require', 'import',
    'export', 'default', 'named', 'from', 'as', 'type', 'typeof', 'instanceof', 'in', 'of', 'new',
    'this', 'super', 'static', 'async', 'await', 'yield', 'function*', 'generator', 'iterator',
    'iterable', 'spread', 'rest', 'destructuring', 'default', 'parameter', 'optional', 'chaining',
    'nullish', 'coalescing', 'optional', 'private', 'public', 'protected', 'readonly', 'abstract',
    'interface', 'type', 'alias', 'enum', 'const', 'enum', 'as', 'const', 'satisfies', 'extends',
    'implements', 'keyof', 'typeof', 'infer', 'extends', 'never', 'unknown', 'any', 'void', 'null',
    'undefined', 'never', 'unknown', 'object', 'Object', 'Function', 'Array', 'String', 'Number',
    'Boolean', 'Symbol', 'BigInt', 'Date', 'RegExp', 'Map', 'Set', 'WeakMap', 'WeakSet', 'Promise',
    'Proxy', 'Reflect', 'Math', 'JSON', 'console', 'process', 'global', 'globalThis', 'window',
    'document', 'navigator', 'location', 'history', 'localStorage', 'sessionStorage', 'indexedDB',
    'fetch', 'XMLHttpRequest', 'WebSocket', 'Worker', 'SharedWorker', 'ServiceWorker', 'BroadcastChannel',
    'MessageChannel', 'Intl', 'DateTimeFormat', 'NumberFormat', 'Collator', 'PluralRules', 'RelativeTimeFormat',
    'ListFormat', 'Segmenter', 'DisplayNames', 'getCanonicalLocales', 'supportedValuesOf',
    'java', 'kotlin', 'scala', 'groovy', 'clojure', 'jvm', 'maven', 'gradle', 'ant', 'ivy', 'sbt',
    'csharp', 'c#', 'fsharp', 'f#', 'visual', 'basic', 'vb.net', '.net', 'dotnet', 'nuget', 'msbuild',
    'c', 'c++', 'cpp', 'objective-c', 'swift', 'rust', 'go', 'golang', 'rust', 'dart', 'flutter',
    'php', 'ruby', 'perl', 'python', 'python3', 'py', 'rb', 'pl', 'php', 'go', 'rs', 'swift', 'kt',
    'dart', 'lua', 'r', 'matlab', 'octave', 'julia', 'haskell', 'ocaml', 'f#', 'scala', 'clojure',
    'erlang', 'elixir', 'gleam', 'zig', 'odin', 'v', 'nim', 'crystal', 'd', 'delphi', 'pascal',
    'fortran', 'cobol', 'lisp', 'scheme', 'racket', 'forth', 'prolog', 'sql', 'pl/sql', 't-sql',
    'pgsql', 'mysql', 'sqlite', 'mongodb', 'redis', 'elasticsearch', 'cassandra', 'dynamodb', 'neo4j',
    'graphql', 'sparql', 'xquery', 'xpath', 'xslt', 'xaml', 'markdown', 'md', 'rst', 'asciidoc',
    'latex', 'tex', 'bibtex', 'html', 'htm', 'xhtml', 'shtml', 'php', 'phtml', 'jsp', 'asp', 'aspx',
    'css', 'scss', 'sass', 'less', 'stylus', 'postcss', 'tailwind', 'bootstrap', 'material', 'antd',
    'element', 'vuetify', 'quasar', 'chakra', 'mui', 'emotion', 'styled-components', 'linaria', 'stitches',
    'jest', 'mocha', 'chai', 'sinon', 'vitest', 'cypress', 'playwright', 'puppeteer', 'selenium',
    'webdriver', 'appium', 'detox', 'karma', 'tape', 'ava', 'tap', 'qunit', 'jasmine', 'vitest',
    'eslint', 'prettier', 'stylelint', 'tslint', 'jshint', 'jslint', 'standard', 'xo', 'rome',
    'biome', 'oxlint', 'dprint', 'clang-format', 'black', 'ruff', 'autopep8', 'yapf', 'gofmt',
    'rustfmt', 'ktlint', 'detekt', 'checkstyle', 'pmd', 'findbugs', 'spotbugs', 'sonarqube', 'codeclimate',
    'git', 'svn', 'mercurial', 'hg', 'fossil', 'perforce', 'tfs', 'vss', 'cvs', 'rcs', 'sccs',
    'github', 'gitlab', 'bitbucket', 'azure', 'devops', 'gitea', 'gogs', 'gitbucket', 'phabricator',
    'jenkins', 'gitlab-ci', 'github-actions', 'circleci', 'travis', 'appveyor', 'codeship', 'drone',
    'buildkite', 'semaphore', 'teamcity', 'bamboo', 'argo', 'tekton', 'flux', 'spinnaker', 'concourse',
    'docker', 'dockerfile', 'docker-compose', 'compose', 'swarm', 'kubernetes', 'k8s', 'helm', 'chart',
    'istio', 'linkerd', 'envoy', 'nginx', 'traefik', 'haproxy', 'varnish', 'squid', 'iptables', 'ufw',
    'firewalld', 'selinux', 'apparmor', 'systemd', 'sysvinit', 'openrc', 'runit', 's6', 'supervisord',
    'monit', 'prometheus', 'grafana', 'alertmanager', 'loki', 'promtail', 'tempo', 'mimir', 'thanos',
    'elasticsearch', 'logstash', 'kibana', 'beats', 'filebeat', 'metricbeat', 'heartbeat', 'packetbeat',
    'auditbeat', 'journalbeat', 'functionbeat', 'splunk', 'datadog', 'newrelic', 'dynatrace', 'appdynamics',
    'sumologic', 'loggly', 'papertrail', 'sentry', 'bugsnag', 'rollbar', 'airbrake', 'honeybadger',
    'opentelemetry', 'otel', 'jaeger', 'zipkin', 'skywalking', 'pinpoint', 'cat', 'dapper', 'zipkin',
    'linux', 'unix', 'posix', 'gnu', 'bsd', 'macos', 'darwin', 'ios', 'ipados', 'watchos', 'tvos',
    'windows', 'win32', 'win64', 'android', 'chromeos', 'fuchsia', 'haiku', 'reactos', 'freebsd',
    'netbsd', 'openbsd', 'dragonfly', 'solaris', 'illumos', 'aix', 'hp-ux', 'irix', 'tru64', 'vms',
    'alpine', 'debian', 'ubuntu', 'fedora', 'rhel', 'centos', 'rocky', 'almalinux', 'oracle', 'suse',
    'opensuse', 'arch', 'manjaro', 'gentoo', 'slackware', 'void', 'artix', 'garuda', 'endeavouros',
    'pop_os', 'elementary', 'mint', 'zorin', 'mx', 'antix', 'puppy', 'tails', 'whonix', 'qubes',
    'raspbian', 'raspberry', 'pi', 'arm', 'arm64', 'aarch64', 'x86', 'x86_64', 'amd64', 'i386', 'i686',
    'riscv', 'riscv64', 'ppc', 'ppc64', 'ppc64le', 's390', 's390x', 'mips', 'mips64', 'mipsel',
    'loongarch', 'loong64', 'wasm', 'wasm32', 'wasm64', 'asm.js', 'webassembly', 'wasi', 'emscripten'
  ])
  
  props.logs.forEach(log => {
    const words = extractWords(log.message)
    words.forEach(word => {
      const lowerWord = word.toLowerCase()
      if (lowerWord.length >= 3 && !stopWords.has(lowerWord) && !/^\d+$/.test(lowerWord)) {
        wordCounts[lowerWord] = (wordCounts[lowerWord] || 0) + 1
      }
    })
  })
  
  const sortedWords = Object.entries(wordCounts)
    .map(([word, count]) => ({ word, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)
  
  return sortedWords
})

const maxKeywordCount = computed(() => {
  if (topKeywords.value.length === 0) return 0
  return topKeywords.value[0].count
})

const maxLevelCount = computed(() => {
  const counts = Object.values(levelStats.value)
  return Math.max(...counts, 1)
})

function detectLogLevel(message) {
  const upperMessage = message.toUpperCase()
  
  if (upperMessage.includes('ERROR') || upperMessage.includes('FATAL') || upperMessage.includes('CRITICAL') || upperMessage.includes('ERR]') || upperMessage.includes('ERROR:')) {
    return 'ERROR'
  }
  if (upperMessage.includes('WARN') || upperMessage.includes('WARNING') || upperMessage.includes('WARN]')) {
    return 'WARN'
  }
  if (upperMessage.includes('INFO') || upperMessage.includes('INFORMATION') || upperMessage.includes('INFO]')) {
    return 'INFO'
  }
  if (upperMessage.includes('DEBUG') || upperMessage.includes('TRACE') || upperMessage.includes('VERBOSE') || upperMessage.includes('DEBUG]')) {
    return 'DEBUG'
  }
  
  return 'UNKNOWN'
}

function extractWords(message) {
  const matches = message.match(/[a-zA-Z]{3,}/g)
  return matches || []
}

function getLevelPercentage(level) {
  if (maxLevelCount.value === 0) return 0
  return (levelStats.value[level] / maxLevelCount.value) * 100
}

function getKeywordPercentage(count) {
  if (maxKeywordCount.value === 0) return 0
  return (count / maxKeywordCount.value) * 100
}

function togglePanel() {
  isExpanded.value = !isExpanded.value
}

function initTrendChart() {
  if (!trendChartRef.value) return
  
  if (trendChart) {
    trendChart.destroy()
  }
  
  const ctx = trendChartRef.value.getContext('2d')
  if (!ctx) return
  
  const trendData = calculateTrendData()
  
  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: trendData.labels,
      datasets: [
        {
          label: 'ERROR',
          data: trendData.error,
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: 'WARN',
          data: trendData.warn,
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245, 158, 11, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: 'INFO',
          data: trendData.info,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.4
        },
        {
          label: 'DEBUG',
          data: trendData.debug,
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          fill: true,
          tension: 0.4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#9ca3af',
            font: { size: 11 }
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false
        }
      },
      scales: {
        x: {
          grid: {
            color: 'rgba(75, 85, 99, 0.3)'
          },
          ticks: {
            color: '#9ca3af',
            maxRotation: 45,
            minRotation: 45,
            font: { size: 10 }
          }
        },
        y: {
          grid: {
            color: 'rgba(75, 85, 99, 0.3)'
          },
          ticks: {
            color: '#9ca3af',
            font: { size: 10 }
          },
          beginAtZero: true
        }
      },
      interaction: {
        mode: 'nearest',
        axis: 'x',
        intersect: false
      }
    }
  })
}

function calculateTrendData() {
  const logs = [...props.logs]
  
  if (logs.length === 0) {
    return {
      labels: [],
      error: [],
      warn: [],
      info: [],
      debug: []
    }
  }
  
  const sortedLogs = logs.sort((a, b) => a.timestamp - b.timestamp)
  
  const startTime = sortedLogs[0].timestamp
  const endTime = sortedLogs[sortedLogs.length - 1].timestamp
  const totalDuration = endTime - startTime
  
  const numBuckets = 10
  const bucketDuration = totalDuration > 0 ? totalDuration / numBuckets : 1
  
  const buckets = Array(numBuckets).fill(null).map(() => ({
    error: 0,
    warn: 0,
    info: 0,
    debug: 0,
    count: 0
  }))
  
  sortedLogs.forEach(log => {
    const level = detectLogLevel(log.message)
    const bucketIndex = totalDuration > 0 
      ? Math.min(Math.floor((log.timestamp - startTime) / bucketDuration), numBuckets - 1)
      : 0
    
    if (level === 'ERROR') buckets[bucketIndex].error++
    else if (level === 'WARN') buckets[bucketIndex].warn++
    else if (level === 'INFO') buckets[bucketIndex].info++
    else if (level === 'DEBUG') buckets[bucketIndex].debug++
    
    buckets[bucketIndex].count++
  })
  
  const labels = buckets.map((_, i) => {
    const bucketTime = startTime + (i + 0.5) * bucketDuration
    return formatShortTime(bucketTime)
  })
  
  return {
    labels,
    error: buckets.map(b => b.error),
    warn: buckets.map(b => b.warn),
    info: buckets.map(b => b.info),
    debug: buckets.map(b => b.debug)
  }
}

function formatShortTime(timestamp) {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

watch(() => props.logs, () => {
  if (isExpanded.value) {
    nextTick(() => {
      initTrendChart()
    })
  }
}, { deep: true })

watch(isExpanded, (newValue) => {
  if (newValue) {
    nextTick(() => {
      initTrendChart()
    })
  }
})

onMounted(() => {
  nextTick(() => {
    if (isExpanded.value) {
      initTrendChart()
    }
  })
})

onUnmounted(() => {
  if (trendChart) {
    trendChart.destroy()
    trendChart = null
  }
})
</script>

<style scoped>
.stats-panel {
  margin-bottom: 1.5rem;
  background-color: var(--bg-primary);
  border-radius: 0.5rem;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background-color: var(--bg-secondary);
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}

.stats-header:hover {
  background-color: rgba(59, 130, 246, 0.1);
}

.stats-title {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.stats-title .icon {
  font-size: 1.1rem;
}

.toggle-icon {
  color: var(--text-secondary);
  font-size: 0.75rem;
  transition: transform 0.3s;
}

.stats-content {
  padding: 1rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.stats-card {
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
  padding: 1rem;
}

.stats-card-full {
  grid-column: 1 / -1;
}

.stats-card h3 {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.level-distribution {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.level-item {
  display: grid;
  grid-template-columns: 60px 50px 1fr;
  align-items: center;
  gap: 0.75rem;
  padding: 0.25rem 0;
}

.level-name {
  font-weight: 600;
  font-size: 0.8125rem;
}

.level-item.level-error .level-name { color: #ef4444; }
.level-item.level-warn .level-name { color: #f59e0b; }
.level-item.level-info .level-name { color: #3b82f6; }
.level-item.level-debug .level-name { color: #10b981; }
.level-item.level-unknown .level-name { color: #6b7280; }

.level-count {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  text-align: right;
}

.level-bar {
  height: 8px;
  background-color: #374151;
  border-radius: 4px;
  overflow: hidden;
}

.level-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.level-item.level-error .level-bar-fill { background-color: #ef4444; }
.level-item.level-warn .level-bar-fill { background-color: #f59e0b; }
.level-item.level-info .level-bar-fill { background-color: #3b82f6; }
.level-item.level-debug .level-bar-fill { background-color: #10b981; }
.level-item.level-unknown .level-bar-fill { background-color: #6b7280; }

.summary-text {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-color);
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.summary-text strong {
  color: var(--text-primary);
}

.error-rate {
  margin-left: 0.5rem;
}

.error-rate strong.high {
  color: #ef4444;
}

.chart-container {
  height: 200px;
  width: 100%;
}

.keywords-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.keyword-item {
  display: grid;
  grid-template-columns: 30px 1fr 50px 120px;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem;
  background-color: var(--bg-primary);
  border-radius: 0.25rem;
  transition: background-color 0.2s;
}

.keyword-item:hover {
  background-color: rgba(59, 130, 246, 0.05);
}

.keyword-rank {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: #374151;
  color: #9ca3af;
}

.keyword-item.rank-1 .keyword-rank {
  background-color: #fbbf24;
  color: #1f2937;
}

.keyword-item.rank-2 .keyword-rank {
  background-color: #9ca3af;
  color: #1f2937;
}

.keyword-item.rank-3 .keyword-rank {
  background-color: #d97706;
  color: #1f2937;
}

.keyword-word {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.keyword-count {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  text-align: right;
}

.keyword-bar {
  height: 6px;
  background-color: #374151;
  border-radius: 3px;
  overflow: hidden;
}

.keyword-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.no-keywords {
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}

.collapse-enter-to,
.collapse-leave-from {
  max-height: 1000px;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .level-item {
    grid-template-columns: 50px 40px 1fr;
    gap: 0.5rem;
  }
  
  .keyword-item {
    grid-template-columns: 24px 1fr 40px 80px;
    gap: 0.5rem;
  }
}
</style>
