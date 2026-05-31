export function createAdminOverviewState() {
  return {
    summary: null,
    history: [],
    live_tasks: [],
    libraries: [],
    recent_failures: [],
    media_snapshot: {
      summary: null,
      items: [],
    },
    maintenance: {
      videos: {},
      duplicates: {},
      tasks: {},
    },
  };
}

export function createDatabaseState() {
  return {
    summary: null,
    shards: [],
  };
}

export function createLibraryState() {
  return {
    username: null,
    taskId: null,
    files: {
      videos: [],
      photos: [],
      documents: [],
    },
  };
}

export function createMediaCenterState() {
  return {
    summary: null,
    items: [],
    filters: {
      username: null,
      media_type: 'video',
      query: '',
      sort: 'latest',
      favorite: null,
      watched: null,
      watch_later: null,
      limit: 120,
    },
  };
}

export function createSearchState() {
  return {
    query: '',
    results: {
      media: [],
      tasks: [],
      history: [],
      users: [],
    },
  };
}

export function createUsernameDirectoryState() {
  return {
    items: [],
  };
}

export function createWorkbenchState() {
  return {
    initialized: false,
    authReady: false,
    auth: {
      loggedIn: false,
      isAdmin: false,
      username: '',
    },
    loading: {
      auth: false,
      tasks: false,
      overview: false,
      adminFiles: false,
      database: false,
      databaseHealth: false,
      databaseDetail: false,
      databaseMigrate: false,
      config: false,
      library: false,
      media: false,
      usernameDirectory: false,
      system: false,
      search: false,
      taskDetail: false,
    },
    tasks: [],
    logs: [
      {
        time: '--:--:--',
        message: '等待开始...',
        level: 'info',
      },
    ],
    progress: {
      text: '准备中...',
      step: '',
      percentage: 0,
    },
    screenshot: {
      url: '',
      unavailable: false,
      taskId: null,
    },
    adminOverview: createAdminOverviewState(),
    adminFiles: {},
    database: createDatabaseState(),
    databaseHealth: createDatabaseState(),
    databaseDetail: null,
    config: null,
    library: createLibraryState(),
    mediaCenter: createMediaCenterState(),
    usernameDirectory: createUsernameDirectoryState(),
    system: null,
    search: createSearchState(),
    taskDetail: null,
  };
}
