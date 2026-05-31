import { createRouter, createWebHistory } from 'vue-router';

const AppLayout = () => import('../layouts/AppLayout.vue');
const HomePage = () => import('../pages/HomePage.vue');
const UserFeedPage = () => import('../pages/UserFeedPage.vue');
const UserPostPage = () => import('../pages/UserPostPage.vue');
const UserVideoPage = () => import('../pages/UserVideoPage.vue');
const DashboardPage = () => import('../pages/DashboardPage.vue');
const DatabasePage = () => import('../pages/DatabasePage.vue');
const DeploymentPage = () => import('../pages/DeploymentPage.vue');
const LibraryPage = () => import('../pages/LibraryPage.vue');
const LoginPage = () => import('../pages/LoginPage.vue');
const MonitorPage = () => import('../pages/MonitorPage.vue');
const NewTaskPage = () => import('../pages/NewTaskPage.vue');
const SearchPage = () => import('../pages/SearchPage.vue');
const SettingsPage = () => import('../pages/SettingsPage.vue');
const TaskDetailPage = () => import('../pages/TaskDetailPage.vue');
const TasksPage = () => import('../pages/TasksPage.vue');

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
      meta: {
        public: true,
      },
    },
    {
      path: '/timeline/:username/video/:tweetId/:videoIndex?',
      alias: '/viewer/feed/:username/video/:tweetId/:videoIndex?',
      name: 'user-video-standalone',
      component: UserVideoPage,
      meta: {
        requiresAuth: true,
        standalone: true,
      },
    },
    {
      path: '/timeline/:username/post/:tweetId',
      alias: '/viewer/feed/:username/post/:tweetId',
      name: 'user-post-standalone',
      component: UserPostPage,
      meta: {
        requiresAuth: true,
        standalone: true,
      },
    },
    {
      path: '/timeline/:username?',
      alias: '/viewer/feed/:username?',
      name: 'user-feed-standalone',
      component: UserFeedPage,
      meta: {
        requiresAuth: true,
        standalone: true,
      },
    },
    {
      path: '/',
      component: AppLayout,
      meta: {
        requiresAuth: true,
      },
      children: [
        {
          path: '',
          redirect: '/new-task',
        },
        {
          path: 'home',
          name: 'home',
          component: HomePage,
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: DashboardPage,
        },
        {
          path: 'new-task',
          name: 'new-task',
          component: NewTaskPage,
        },
        {
          path: 'tasks',
          name: 'tasks',
          component: TasksPage,
        },
        {
          path: 'tasks/:taskId',
          name: 'task-detail',
          component: TaskDetailPage,
        },
        {
          path: 'feed/:username/video/:tweetId/:videoIndex?',
          name: 'user-video',
          component: UserVideoPage,
        },
        {
          path: 'feed/:username/post/:tweetId',
          name: 'user-post',
          component: UserPostPage,
        },
        {
          path: 'feed/:username?',
          name: 'user-feed',
          component: UserFeedPage,
        },
        {
          path: 'library',
          name: 'library',
          component: LibraryPage,
        },
        {
          path: 'search',
          name: 'search',
          component: SearchPage,
        },
        {
          path: 'database',
          name: 'database',
          component: DatabasePage,
        },
        {
          path: 'monitor',
          name: 'monitor',
          component: MonitorPage,
        },
        {
          path: 'settings',
          name: 'settings',
          component: SettingsPage,
        },
        {
          path: 'deployment',
          name: 'deployment',
          component: DeploymentPage,
        },
      ],
    },
    {
      path: '/admin',
      redirect: '/dashboard',
    },
    {
      path: '/admin/login',
      redirect: '/login',
    },
  ],
});

export default router;
