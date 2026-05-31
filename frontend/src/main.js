import { createApp } from 'vue';
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  Collapse,
  ConfigProvider,
  Descriptions,
  Divider,
  Drawer,
  Dropdown,
  Empty,
  Form,
  Image,
  Input,
  InputNumber,
  Layout,
  List,
  Menu,
  Modal,
  Popconfirm,
  Progress,
  Radio,
  Result,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Steps,
  Table,
  Tabs,
  Tag,
  Timeline,
  Typography,
} from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';

import App from './App.vue';
import router from './router';
import './styles/app.css';
import './styles/theme-overrides.css';

const app = createApp(App);

app.use(router);
[
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  Collapse,
  ConfigProvider,
  Descriptions,
  Divider,
  Drawer,
  Dropdown,
  Empty,
  Form,
  Image,
  Input,
  InputNumber,
  Layout,
  List,
  Menu,
  Modal,
  Popconfirm,
  Progress,
  Radio,
  Result,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Steps,
  Table,
  Tabs,
  Tag,
  Timeline,
  Typography,
].forEach((component) => {
  app.use(component);
});
app.mount('#app');
