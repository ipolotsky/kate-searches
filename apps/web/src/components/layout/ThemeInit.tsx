import { StoreInit } from "flowbite-react/store/init";

// Синхронизирует runtime-стор flowbite-react с конфигом (Tailwind v3, без prefix).
// Без этого компоненты используют дефолты (версия 4) и часть классов резолвится неверно.
// Аналог авто-генерируемого .flowbite-react/init.tsx, но без зависимости от gitignored файла.
export const ThemeInit: React.FC = () => <StoreInit dark prefix="" version={3} />;
