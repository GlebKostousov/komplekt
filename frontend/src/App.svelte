<script lang="ts">
  import { onMount } from 'svelte';
  import { api, problemFrom } from './lib/api';
  import type { ApiProblem, ImportKind, Page, Product, State } from './lib/types';
  import { applyState, workspace } from './lib/workspace.svelte';
  import Icon from './components/Icon.svelte';
  import Modal from './components/Modal.svelte';
  import Problem from './components/Problem.svelte';
  import FileGuide from './components/FileGuide.svelte';
  import PriceEditor from './components/PriceEditor.svelte';
  import RequestPage from './pages/RequestPage.svelte';
  import PricePage from './pages/PricePage.svelte';
  import QuotePage from './pages/QuotePage.svelte';
  import HistoryPage from './pages/HistoryPage.svelte';
  let page = $state<Page>('price');
  let requestId = $state('');
  let loading = $state(true);
  let problem = $state<ApiProblem | null>(null);
  let guide = $state<ImportKind | null>(null);
  let priceProduct = $state<Product | null>(null);
  let showAbout = $state(false);
  let mobileMenu = $state(false);
  let toast = $state('');
  let toastTimer: ReturnType<typeof setTimeout>;
  const pages: { id: Page; title: string; icon: string }[] = [
    { id: 'price', title: 'Прайс', icon: 'price' },
    { id: 'requests', title: 'Заявки', icon: 'requests' },
    { id: 'quote', title: 'Подготовка КП', icon: 'quote' },
    { id: 'history', title: 'История КП', icon: 'history' },
  ];
  function readRoute() {
    const [next, id] = location.hash.replace(/^#\/?/, '').split('/');
    if (pages.some((item) => item.id === next)) page = next as Page;
    if (id) {
      try {
        requestId = decodeURIComponent(id);
      } catch {
        requestId = '';
      }
    }
    mobileMenu = false;
  }
  function navigate(next: Page, id?: string) {
    if (id) requestId = id;
    page = next;
    mobileMenu = false;
    location.hash = `${next}${next === 'quote' && requestId ? `/${encodeURIComponent(requestId)}` : ''}`;
    window.scrollTo({ top: 0, behavior: 'instant' });
  }
  function notify(message: string) {
    toast = message;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast = ''), 4000);
  }
  async function load() {
    loading = true;
    problem = null;
    try {
      applyState(await api<State>('/state'));
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      loading = false;
    }
  }
  onMount(() => {
    readRoute();
    void load();
    window.addEventListener('hashchange', readRoute);
    return () => {
      window.removeEventListener('hashchange', readRoute);
      clearTimeout(toastTimer);
    };
  });
  function acceptState(next: State) {
    applyState(next);
  }
</script>

<svelte:head><title>{pages.find((item) => item.id === page)?.title} · Комплект</title></svelte:head>
<a href="#main" class="skip-link">Перейти к содержимому</a>
<div class="app-shell">
  <aside class:mobile-open={mobileMenu} class="sidebar">
    <a href="#price" class="wordmark" onclick={() => navigate('price')}
      ><span class="brand-mark"><span></span><span></span></span><span
        >комплект<span class="brand-descriptor">Коммерческие предложения</span></span
      ></a
    >
    <div class="sidebar-caption">Рабочее пространство</div>
    <nav aria-label="Основная навигация">
      {#each pages as item}<a
          href={`#${item.id}`}
          class:active={page === item.id}
          aria-current={page === item.id ? 'page' : undefined}
          onclick={(event) => {
            event.preventDefault();
            navigate(item.id);
          }}
          ><Icon name={item.icon} size={20} /><span>{item.title}</span
          >{#if item.id === 'requests' && workspace.state?.requests.length}<small
              >{workspace.state.requests.length}</small
            >{:else if item.id === 'history' && workspace.state?.quotes.length}<small
              >{workspace.state.quotes.length}</small
            >{/if}</a
        >{/each}
    </nav>
    <div class="sidebar-bottom">
      <button class="sidebar-help" onclick={() => (guide = page === 'price' ? 'price' : 'request')}
        ><Icon name="book" size={19} /><span>Как подготовить файлы</span></button
      ><button class="demo-card" onclick={() => (showAbout = true)}
        ><span class="demo-caption"><span></span>Учебная версия<Icon name="info" size={15} /></span>
        <p>Без входа и разграничения доступа. Используйте вымышленные данные.</p>
        <span class="demo-more">О тестовом задании<Icon name="arrow" size={15} /></span></button
      >
      <div class="sidebar-credit">ПрофЛаб<span>Практическое задание</span></div>
    </div>
  </aside>
  <div class="main-shell">
    <div class="topbar">
      <div class="breadcrumb">
        <button
          class="icon-button mobile-toggle"
          onclick={() => (mobileMenu = !mobileMenu)}
          aria-label="Открыть меню"
          aria-expanded={mobileMenu}><Icon name="menu" /></button
        ><span>Комплект</span><Icon name="chevron" size={13} /><b
          >{pages.find((item) => item.id === page)?.title}</b
        >
      </div>
      <button class="topbar-demo" onclick={() => (showAbout = true)}
        ><span class="live-dot"></span>Локальное приложение<Icon name="info" size={14} /></button
      >
    </div>
    <main id="main" tabindex="-1">
      {#if loading}<div class="app-loading">
          <span class="spinner"></span>
          <h2>Открываем сохранённые данные</h2>
          <p>Загружаем сохранённый прайс и заявки.</p>
        </div>{:else if problem}<section class="panel load-error">
          <Problem {problem} /><button class="button primary" onclick={load}
            ><Icon name="refresh" size={18} />Попробовать ещё раз</button
          >
        </section>{:else if workspace.state}{#if page === 'requests'}<RequestPage
            appState={workspace.state}
            onstate={acceptState}
            onnavigate={navigate}
            onguide={(kind) => (guide = kind)}
          />{:else if page === 'price'}<PricePage
            appState={workspace.state}
            onstate={acceptState}
            onguide={(kind) => (guide = kind)}
            onpriceedit={(product) => (priceProduct = product)}
            onnavigate={navigate}
          />{:else if page === 'quote'}<QuotePage
            appState={workspace.state}
            {requestId}
            onstate={acceptState}
            onrequestchange={(id) => navigate('quote', id)}
            onnavigate={navigate}
            onpriceedit={(product) => (priceProduct = product)}
          />{:else}<HistoryPage appState={workspace.state} onnavigate={navigate} />{/if}{/if}
    </main>
    <footer class="app-footer">
      <span>Комплект · тестовое задание</span><span>CSV → проверка → коммерческое предложение</span>
    </footer>
  </div>
</div>
{#if toast}<div class="toast" role="status"><Icon name="circleCheck" size={19} />{toast}</div>{/if}
{#if guide}<FileGuide initial={guide} onclose={() => (guide = null)} />{/if}
{#if priceProduct && workspace.state}<PriceEditor
    product={priceProduct}
    appState={workspace.state}
    onstate={acceptState}
    onclose={() => (priceProduct = null)}
    onsaved={() => notify('Цена сохранена. Расчёт обновлён.')}
  />{/if}
{#if showAbout}<Modal
    title="О тестовом задании"
    subtitle="Что умеет этот пример и где его граница."
    onclose={() => (showAbout = false)}
    ><div class="assumption-list">
      <section>
        <h3>Без входа</h3>
        <p>Кто открыл приложение, видит и меняет общие данные. Реквизиты только вымышленные.</p>
      </section>
      <section>
        <h3>Только CSV</h3>
        <p>
          Заявки и прайсы загружаются из CSV UTF-8 с разделителем «;». Excel и PDF не принимаются.
        </p>
      </section>
      <section>
        <h3>Новый прайс заменяет старый</h3>
        <p>
          Прежние товары удаляются. Ручные цены и подобранные соответствия сбрасываются. Выпущенные
          PDF остаются.
        </p>
      </section>
      <section>
        <h3>Цена меняется у товара</h3>
        <p>Правка сразу входит в расчёт заявок. Уже сохранённый PDF не пересчитывается.</p>
      </section>
      <section>
        <h3>Условия расчёта</h3>
        <p>
          Рубли, скидка 10% и НДС 20% заданы заданием. Количество в заявке — в штуках, продажа —
          целыми упаковками.
        </p>
      </section>
      <section>
        <h3>Продавец задан</h3>
        <p>
          «Ладога Комплект Демо» и её реквизиты вымышлены. Предмет и условия фиксированы. Покупателю
          КП само не отправляется.
        </p>
      </section>
    </div></Modal
  >{/if}
