---
title: Dependency-Based Parallelization
impact: CRITICAL
impactDescription: 2-10× improvement
tags: async, parallelization, dependencies, better-all
---

## Dependency-Based Parallelization

For operations with partial dependencies, use `better-all` to maximize parallelism. It automatically starts each task at the earliest possible moment.

**Incorrect (profile waits for config unnecessarily):**

```typescript
const [user, config] = await Promise.all([
  fetchUser(),
  fetchConfig()
])
const profile = await fetchProfile(user.id)
```

**Correct (plain Promise — config and profile run in parallel):**

```typescript
const userPromise = fetchUser()
const configPromise = fetchConfig()   // independent of profile — keep in flight
const user = await userPromise        // profile needs ONLY user
const [config, profile] = await Promise.all([
  configPromise,
  fetchProfile(user.id)
])
```

**Correct (with `better-all`, if already a dependency):**

```typescript
import { all } from 'better-all'

const { user, config, profile } = await all({
  async user() { return fetchUser() },
  async config() { return fetchConfig() },
  async profile() {
    return fetchProfile((await this.$.user).id)
  }
})
```

**Misconception:** `Promise.all` does not make a route optimal. `profile` depends
on `user` but NOT on `config`; batching `config` into the group that gates
`profile` puts the slower sibling on `profile`'s critical path for nothing. Await
only what a call consumes; start everything else in parallel with it.

Reference: [https://github.com/shuding/better-all](https://github.com/shuding/better-all)
