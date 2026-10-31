import { useState } from 'react';
import {
  Alert,
  Button,
  Modal,
  NumberInput,
  PasswordInput,
  SegmentedControl,
  Select,
  Skeleton,
  Switch,
} from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, ChevronRight, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import { RESEARCH_MODES } from '../lib/modes';
import type { AppSettings, KeyName, ModelTask, ResearchMode, SettingsUpdate } from '../lib/types';

const KEYS: { name: KeyName; label: string; detail: string }[] = [
  {
    name: 'meta_api_key',
    label: 'Meta API key',
    detail: 'Muse models that separate claims, read images and assess evidence.',
  },
  {
    name: 'tavily_api_key',
    label: 'Tavily API key',
    detail: 'Web search and page reading. Without a key, rate-limited keyless access is used.',
  },
  {
    name: 'serp_api_key',
    label: 'SerpApi key',
    detail: 'Reverse image search with Google Lens and Bing.',
  },
  {
    name: 'google_fact_check_api_key',
    label: 'Google Fact Check key',
    detail: 'Earlier fact checks of an image or caption.',
  },
];

const TASKS: { task: ModelTask; label: string }[] = [
  { task: 'claim_extraction', label: 'Claim extraction' },
  { task: 'screenshot', label: 'Image reading' },
  { task: 'research', label: 'Research planning' },
  { task: 'judge', label: 'Evidence judging' },
];

const ADVANCED = [
  'default_research_mode',
  'reverse_image_search',
  'fact_check_search',
  'link_reading',
  'search_min_score',
] as const;

type Advanced = Pick<AppSettings, (typeof ADVANCED)[number]>;

const RESET_ALL = [
  ...KEYS.map(({ name }) => name),
  ...TASKS.map(({ task }) => `model_${task}`),
  'paid_calls',
  ...ADVANCED,
];

function keyStatus(settings: AppSettings, name: KeyName) {
  const status = settings.keys[name];
  if (!status.configured) return 'Not set';
  // A key that differs from .env gets its own note below the field.
  const origin = status.source === 'panel' ? 'Set' : 'Same as .env';
  return status.preview ? (
    <>
      {origin} · <code className="settings-key-preview">{status.preview}</code>
    </>
  ) : (
    origin
  );
}

/** Marks a saved value that differs from .env and lets the user take the .env value again. */
function EnvNote({
  field,
  settings,
  resets,
  onToggle,
}: {
  field: string;
  settings: AppSettings;
  resets: string[];
  onToggle: (field: string) => void;
}) {
  const resetting = resets.includes(field);
  if (!resetting && !settings.changed.includes(field)) return null;
  return (
    <div className="settings-env-note">
      <span>
        {resetting ? 'Takes the .env value after saving' : 'Saved here · differs from .env'}
      </span>
      <button type="button" className="text-button" onClick={() => onToggle(field)}>
        {resetting ? 'Undo' : 'Use .env value'}
      </button>
    </div>
  );
}

/** Settings saved on the server. Keys are write-only: entered here, never shown again. */
export function SettingsPage() {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);
  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: ({ signal }) => api.settings(signal),
  });
  const save = useMutation({
    mutationFn: api.saveSettings,
    retry: false,
    onSuccess: (updated) => {
      queryClient.setQueryData(['settings'], updated);
      void queryClient.invalidateQueries({ queryKey: ['health'] });
      setSaved(true);
    },
    onMutate: () => setSaved(false),
  });

  return (
    <div className="settings-page">
      <h1>Settings</h1>
      <p className="settings-intro">
        Settings start from <code>.env</code> and are then kept on your server. Changes apply from
        the next investigation, without a restart; later <code>.env</code> edits are marked here
        instead of replacing saved values. Keys are never shown again.
      </p>
      {settings.isPending ? (
        <div aria-label="Loading settings">
          <Skeleton height={90} mb={18} />
          <Skeleton height={260} mb={18} />
          <Skeleton height={180} />
        </div>
      ) : settings.isError ? (
        <div className="error-state">
          <h2>Settings couldn’t be loaded</h2>
          <Button
            variant="default"
            leftSection={<RefreshCw size={14} />}
            onClick={() => void settings.refetch()}
          >
            Try again
          </Button>
        </div>
      ) : (
        <>
          {settings.data.error && (
            <Alert color="orange" title="Saved settings were not applied" mb={18}>
              {settings.data.error} The server is using the values from .env.
            </Alert>
          )}
          <PaidCalls
            settings={settings.data}
            isSaving={save.isPending}
            onSave={(paid) => save.mutateAsync({ paid_calls: paid })}
          />
          <SettingsForm
            key={settings.dataUpdatedAt}
            settings={settings.data}
            isSaving={save.isPending}
            onSave={(changes) => save.mutateAsync(changes)}
          />
          <div aria-live="polite">
            {save.isError && (
              <Alert color="red" title="Settings were not saved" role="alert" mt={18}>
                {save.error.message} Your entries have been kept.
              </Alert>
            )}
            {saved && !save.isPending && (
              <p className="settings-saved">
                <Check size={15} /> Saved. The next investigation uses these settings.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function PaidCalls({
  settings,
  isSaving,
  onSave,
}: {
  settings: AppSettings;
  isSaving: boolean;
  onSave: (paid: boolean) => Promise<unknown>;
}) {
  const [confirming, setConfirming] = useState(false);
  const metaKey = settings.keys.meta_api_key.configured;
  return (
    <section className="settings-section" aria-labelledby="paid-calls-title">
      <div className="settings-row">
        <div>
          <h2 id="paid-calls-title">Allow paid calls</h2>
          <p className="muted">
            {settings.paid_calls
              ? 'Investigations call Meta and the research services with your keys and use credits.'
              : 'Preview mode: investigations make no external calls and use no credits.'}
            {!metaKey && ' Add a Meta API key before allowing paid calls.'}
          </p>
          {settings.changed.includes('paid_calls') && (
            <div className="settings-env-note">
              <span>Saved here · differs from .env</span>
            </div>
          )}
        </div>
        <Switch
          aria-labelledby="paid-calls-title"
          checked={settings.paid_calls}
          disabled={isSaving || (!settings.paid_calls && !metaKey)}
          onChange={(event) =>
            event.currentTarget.checked ? setConfirming(true) : void onSave(false).catch(() => {})
          }
        />
      </div>
      <Modal
        opened={confirming}
        onClose={() => setConfirming(false)}
        title="Allow paid calls?"
        centered
        closeButtonProps={{ 'aria-label': 'Cancel' }}
      >
        <p className="settings-modal-text">
          New investigations will call Meta, Tavily and the image services with your keys, which
          uses credits. An investigation still starts only when you press Investigate.
        </p>
        <div className="settings-actions">
          <Button variant="default" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
          <Button
            loading={isSaving}
            onClick={() =>
              void onSave(true)
                .then(() => setConfirming(false))
                .catch(() => setConfirming(false))
            }
          >
            Allow paid calls
          </Button>
        </div>
      </Modal>
    </section>
  );
}

function SettingsForm({
  settings,
  isSaving,
  onSave,
}: {
  settings: AppSettings;
  isSaving: boolean;
  onSave: (changes: SettingsUpdate) => Promise<unknown>;
}) {
  const [keys, setKeys] = useState<Partial<Record<KeyName, string>>>({});
  const [resets, setResets] = useState<string[]>([]);
  const [confirmingReset, setConfirmingReset] = useState(false);
  const toggleReset = (field: string) =>
    setResets((current) =>
      current.includes(field) ? current.filter((item) => item !== field) : [...current, field],
    );
  const [models, setModels] = useState(settings.models);
  const [advanced, setAdvanced] = useState<Advanced>(() => pickAdvanced(settings));

  const changes: SettingsUpdate = {};
  for (const { name } of KEYS) {
    const value = keys[name]?.trim();
    if (value) changes[name] = value;
  }
  for (const { task } of TASKS) {
    if (models[task] !== settings.models[task]) changes[`model_${task}`] = models[task];
  }
  for (const field of ADVANCED) {
    if (advanced[field] !== settings[field]) Object.assign(changes, { [field]: advanced[field] });
  }
  // A field set back to .env sends null, which the server replaces with the .env value.
  for (const field of resets) Object.assign(changes, { [field]: null });
  const dirty = Object.keys(changes).length > 0;
  const note = (field: string) => (
    <EnvNote field={field} settings={settings} resets={resets} onToggle={toggleReset} />
  );
  const options = settings.model_options.map(({ alias, name }) => ({ value: alias, label: name }));

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (dirty && !isSaving) void onSave(changes).catch(() => {});
      }}
    >
      <section className="settings-section" aria-labelledby="keys-title">
        <h2 id="keys-title">API keys</h2>
        <div className="settings-fields">
          {KEYS.map(({ name, label, detail }) => {
            return (
              <div key={name} className="settings-key">
                <PasswordInput
                  label={label}
                  description={detail}
                  placeholder={
                    settings.keys[name].configured ? 'Enter a new key to replace it' : 'Enter key'
                  }
                  autoComplete="off"
                  spellCheck={false}
                  value={keys[name] ?? ''}
                  onChange={(event) => {
                    const value = event.currentTarget.value;
                    setKeys((current) => ({ ...current, [name]: value }));
                  }}
                />
                <div className="settings-key-status">
                  <span className={settings.keys[name].configured ? 'is-set' : ''}>
                    {keyStatus(settings, name)}
                  </span>
                </div>
                {note(name)}
              </div>
            );
          })}
        </div>
      </section>

      <section className="settings-section" aria-labelledby="models-title">
        <h2 id="models-title">Models</h2>
        <p className="muted">Only models allowed for text investigations are listed.</p>
        <div className="settings-grid">
          {TASKS.map(({ task, label }) => (
            <div key={task}>
              <Select
                label={label}
                data={options}
                value={models[task]}
                allowDeselect={false}
                onChange={(value) =>
                  value && setModels((current) => ({ ...current, [task]: value }))
                }
              />
              {note(`model_${task}`)}
            </div>
          ))}
        </div>
      </section>

      <details className="settings-section settings-advanced">
        <summary>
          <ChevronRight size={16} aria-hidden="true" /> Advanced settings
        </summary>
        <div className="settings-fields">
          <div>
            <span className="settings-label" id="default-mode-label">
              Default research depth
            </span>
            <SegmentedControl
              aria-labelledby="default-mode-label"
              value={advanced.default_research_mode}
              onChange={(value) =>
                setAdvanced((current) => ({
                  ...current,
                  default_research_mode: value as ResearchMode,
                }))
              }
              data={RESEARCH_MODES.map(({ value, label }) => ({ value, label }))}
            />
            {note('default_research_mode')}
          </div>
          <div>
            <Switch
              label="Reverse image search"
              description={
                settings.keys.serp_api_key.configured
                  ? 'Look for earlier copies of an image with Google Lens and Bing.'
                  : 'Look for earlier copies of an image with Google Lens and Bing. Needs a SerpApi key.'
              }
              checked={advanced.reverse_image_search}
              onChange={(event) => {
                const checked = event.currentTarget.checked;
                setAdvanced((current) => ({ ...current, reverse_image_search: checked }));
              }}
            />
            {note('reverse_image_search')}
          </div>
          <div>
            <Switch
              label="Fact check search"
              description="Search Google Fact Check Tools for earlier checks of an image or caption."
              checked={advanced.fact_check_search}
              onChange={(event) => {
                const checked = event.currentTarget.checked;
                setAdvanced((current) => ({ ...current, fact_check_search: checked }));
              }}
            />
            {note('fact_check_search')}
          </div>
          <div>
            <Switch
              label="Read links"
              description="Open links in the text and research the pages they point to."
              checked={advanced.link_reading}
              onChange={(event) => {
                const checked = event.currentTarget.checked;
                setAdvanced((current) => ({ ...current, link_reading: checked }));
              }}
            />
            {note('link_reading')}
          </div>
          <div>
            <NumberInput
              label="Search score threshold"
              description="Search results scored below this are not read. At 0.30, only unrelated pages were dropped in our measurements."
              min={0}
              max={1}
              step={0.05}
              decimalScale={2}
              clampBehavior="strict"
              value={advanced.search_min_score}
              onChange={(value) =>
                typeof value === 'number' &&
                setAdvanced((current) => ({ ...current, search_min_score: value }))
              }
              maw={220}
            />
            {note('search_min_score')}
          </div>
        </div>
      </details>

      <div className="settings-actions settings-footer">
        <Button
          variant="subtle"
          color="gray"
          className="settings-reset-all"
          disabled={isSaving}
          onClick={() => setConfirmingReset(true)}
        >
          Reset all to .env
        </Button>
        <Button type="submit" disabled={!dirty} loading={isSaving}>
          Save changes
        </Button>
      </div>
      <Modal
        opened={confirmingReset}
        onClose={() => setConfirmingReset(false)}
        title="Reset all settings to .env?"
        centered
        closeButtonProps={{ 'aria-label': 'Cancel' }}
      >
        <p className="settings-modal-text">
          Keys, models, paid calls and advanced settings take their current values from .env. Keys
          saved only here are removed, and unsaved changes on this page are discarded.
        </p>
        <div className="settings-actions">
          <Button variant="default" onClick={() => setConfirmingReset(false)}>
            Cancel
          </Button>
          <Button
            color="red"
            loading={isSaving}
            onClick={() =>
              void onSave(Object.fromEntries(RESET_ALL.map((field) => [field, null])))
                .then(() => setConfirmingReset(false))
                .catch(() => setConfirmingReset(false))
            }
          >
            Reset all
          </Button>
        </div>
      </Modal>
    </form>
  );
}

function pickAdvanced(settings: AppSettings): Advanced {
  return {
    default_research_mode: settings.default_research_mode,
    reverse_image_search: settings.reverse_image_search,
    fact_check_search: settings.fact_check_search,
    link_reading: settings.link_reading,
    search_min_score: settings.search_min_score,
  };
}
