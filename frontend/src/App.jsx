
import React, { useEffect, useRef, useState } from 'react';
import { api, WS } from './api';

import {
  Activity,
  LayoutDashboard,
  Ticket,
  Users,
  Monitor,
  PhoneCall,
  RefreshCw,
  CheckCircle,
  SkipForward,
  Volume2,
  Stethoscope
} from 'lucide-react';

// Safely extract arrays from API responses
function getArray(data, keys = []) {
  if (Array.isArray(data)) return data;

  if (data && typeof data === 'object') {
    for (const key of keys) {
      if (Array.isArray(data[key])) return data[key];
    }

    if (Array.isArray(data.data)) return data.data;
    if (Array.isArray(data.results)) return data.results;
  }

  return [];
}

export default function App() {
  const [page, P] = useState('overview');

  const [services, S] = useState([]);
  const [counters, C] = useState([]);
  const [queue, Q] = useState([]);
  const [stats, T] = useState({});
  const [msg, M] = useState('');

  const [form, F] = useState({
    customer_name: '',
    phone: '',
    service_id: '',
    counter_id: ''
  });

  const [mine, N] = useState(null);
  const [last, L] = useState(null);
  const [lang, G] = useState('bn');

  const lastAnnounced = useRef('');
  const langRef = useRef(lang);

  langRef.current = lang;

  // GET COUNTERS FOR SELECTED SERVICE
  function getServiceCounters(counterList, serviceId) {
    return counterList.filter(c =>
      !c.service_id ||
      String(c.service_id) === String(serviceId)
    );
  }

  // LOAD DATA
  async function load() {
    const results = await Promise.allSettled([
      api('/api/services'),
      api('/api/counters'),
      api('/api/queue'),
      api('/api/stats', { admin: true })
    ]);

    let errors = [];

    // SERVICES
    if (results[0].status === 'fulfilled') {
      const serviceList = getArray(
        results[0].value,
        ['services']
      );

      S(serviceList);

      if (!serviceList.length) {
        errors.push('No active services found.');
      }
    } else {
      console.error('Services API Error:', results[0].reason);
      errors.push('Could not load services.');
    }

    // COUNTERS
    if (results[1].status === 'fulfilled') {
      const counterList = getArray(
        results[1].value,
        ['counters']
      );

      C(counterList);

      if (!counterList.length) {
        errors.push('No active counters found.');
      }
    } else {
      console.error('Counters API Error:', results[1].reason);
      errors.push('Could not load counters.');
    }

    // QUEUE
    if (results[2].status === 'fulfilled') {
      Q(getArray(results[2].value, ['queue', 'tokens']));
    } else {
      console.error('Queue API Error:', results[2].reason);
    }

    // STATISTICS
    if (results[3].status === 'fulfilled') {
      T(results[3].value || {});
    } else {
      console.error('Stats API Error:', results[3].reason);
    }

    // AUTOMATICALLY SELECT VALID SERVICE AND COUNTER
    if (
      results[0].status === 'fulfilled' &&
      results[1].status === 'fulfilled'
    ) {
      const serviceList = getArray(
        results[0].value,
        ['services']
      );

      const counterList = getArray(
        results[1].value,
        ['counters']
      );

      F(f => {
        const validService = serviceList.some(
          s => String(s.id) === String(f.service_id)
        );

        const selectedService = validService
          ? String(f.service_id)
          : String(serviceList[0]?.id || '');

        const availableCounters = getServiceCounters(
          counterList,
          selectedService
        );

        const validCounter = availableCounters.some(
          c => String(c.id) === String(f.counter_id)
        );

        const selectedCounter = validCounter
          ? String(f.counter_id)
          : String(availableCounters[0]?.id || '');

        return {
          ...f,
          service_id: selectedService,
          counter_id: selectedCounter
        };
      });
    }

    if (errors.length) {
      M(errors.join(' '));
    }
  }

  // SPEAKER ANNOUNCEMENT
  function announce(t) {
    if (!t || !window.speechSynthesis) return;

    const announcementId = `${t.id}-${t.call_count}`;

    if (lastAnnounced.current === announcementId) return;

    lastAnnounced.current = announcementId;

    window.speechSynthesis.cancel();

    const patientName = t.customer_name || 'Patient';
    const tokenNumber = t.token_number || '';
    const counterName = t.counter_name || 'Room';

    const text = langRef.current === 'bn'
      ? `পরবর্তী রোগী ${patientName}। আপনার টোকেন নম্বর ${tokenNumber.replace('-', ' ')}। অনুগ্রহ করে ${counterName} এ আসুন।`
      : `Next patient, ${patientName}. Token number ${tokenNumber}. Please proceed to ${counterName}.`;

    const utterance = new SpeechSynthesisUtterance(text);

    utterance.lang = langRef.current === 'bn' ? 'bn-BD' : 'en-US';
    utterance.rate = 0.85;
    utterance.pitch = 1;

    window.speechSynthesis.speak(utterance);
  }

  // WEBSOCKET + AUTO REFRESH
  useEffect(() => {
    load();

    const interval = setInterval(load, 5000);

    const ws = new WebSocket(WS);

    ws.onmessage = e => {
      try {
        const d = JSON.parse(e.data);

        if (d.type === 'token_called' && d.token) {
          L(d.token);
          announce(d.token);
        }

        load();
      } catch (error) {
        console.log('WebSocket message error:', error);
      }
    };

    ws.onerror = () => {
      console.log('WebSocket connection error');
    };

    return () => {
      clearInterval(interval);
      ws.close();
    };
  }, []);

  // API ACTION
  async function act(path, body = {}, admin = true) {
    try {
      const d = await api(path, {
        method: 'POST',
        body: JSON.stringify(body),
        admin
      });

      const calledToken =
        d?.token ||
        (d?.id && d?.status === 'serving' ? d : null);

      if (calledToken) {
        L(calledToken);
        announce(calledToken);
      }

      M(d?.message || 'Action completed successfully.');

      await load();

      return d;
    } catch (e) {
      M(e.message);
      return null;
    }
  }

  // BOOK TOKEN
  async function book(e) {
    e.preventDefault();

    if (!form.service_id || !form.counter_id) {
      M('Please select a Service and Counter first.');
      return;
    }

    try {
      const d = await api('/api/book', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          service_id: Number(form.service_id),
          counter_id: Number(form.counter_id)
        })
      });

      N(d);
      M('Token booked successfully.');

      await load();
    } catch (e) {
      M(e.message);
    }
  }

  // NAVIGATION
  const nav = [
    ['overview', 'Overview', LayoutDashboard],
    ['book', 'Book Token', Ticket],
    ['staff', 'Staff Dashboard', Users],
    ['doctor', 'Doctor Dashboard', Stethoscope],
    ['display', 'Display Screen', Monitor]
  ];

  // FILTERED COUNTERS
  const availableCounters = getServiceCounters(
    counters,
    form.service_id
  );

  return (
    <div className="shell">

      {/* SIDEBAR */}
      <aside>
        <div className="brand">
          <Activity />
          <b>QueueLess <i>BD</i></b>
        </div>

        <div className="tag">
          SMART QUEUE AUTOMATION
        </div>

        {nav.map(([id, name, Icon]) => (
          <button
            key={id}
            className={page === id ? 'sel' : ''}
            onClick={() => P(id)}
          >
            <Icon size={18} />
            {name}
          </button>
        ))}

        <div className="asidebottom">
          ● System online
          <br />
          <small>Full-stack MVP · v1.1</small>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main>

        <header>
          <div>
            <small>QUEUE MANAGEMENT PLATFORM</small>
            <h1>{nav.find(x => x[0] === page)[1]}</h1>
          </div>

          <span className="live">● LIVE</span>
        </header>

        {/* MESSAGE */}
        {msg && (
          <div className="msg">
            {msg}
            <button onClick={() => M('')}>×</button>
          </div>
        )}

        {/* OVERVIEW */}
        {page === 'overview' && (
          <>
            <div className="hero">
              <div>
                <small>WELCOME BACK, ADMIN</small>
                <h2>Every queue, under control.</h2>
                <p>
                  Real-time service operations and smarter waiting experiences.
                </p>
              </div>

              <button
                className="primary"
                onClick={() => P('doctor')}
              >
                Doctor Dashboard →
              </button>
            </div>

            <div className="stats">
              {[
                ['Waiting', stats.waiting],
                ['Serving', stats.serving],
                ['Completed', stats.completed],
                ['Skipped', stats.skipped]
              ].map(x => (
                <div className="stat" key={x[0]}>
                  <small>{x[0]}</small>
                  <b>{x[1] ?? 0}</b>
                  <em>LIVE COUNT</em>
                </div>
              ))}
            </div>

            <section>
              <h3>Live Queue</h3>
              <Queue rows={queue} />
            </section>

            <section>
              <h3>Service Counters</h3>

              <div className="cards">
                {counters.map(c => (
                  <div className="counter" key={c.id}>
                    <b>{c.name}</b>

                    <small>
                      {services.find(
                        s => Number(s.id) === Number(c.service_id)
                      )?.name || 'General Counter'}
                    </small>

                    <p>
                      {queue.filter(
                        t => Number(t.counter_id) === Number(c.id)
                      ).length} active patients
                    </p>
                  </div>
                ))}

                {!counters.length && (
                  <p>No active counters available.</p>
                )}
              </div>
            </section>
          </>
        )}

        {/* BOOK TOKEN */}
        {page === 'book' && (
          <section className="formbox">

            <small>PATIENT / CUSTOMER PORTAL</small>
            <h2>Get your token</h2>

            <p>
              Book online and check your estimated waiting time.
            </p>

            <form onSubmit={book}>

              <label>
                Full name
                <input
                  required
                  minLength="2"
                  value={form.customer_name}
                  onChange={e =>
                    F({ ...form, customer_name: e.target.value })
                  }
                />
              </label>

              <label>
                Phone (optional)
                <input
                  value={form.phone}
                  onChange={e =>
                    F({ ...form, phone: e.target.value })
                  }
                />
              </label>

              <label>
                Service

                <select
                  required
                  value={form.service_id}
                  onChange={e => {
                    const serviceId = e.target.value;

                    const matchingCounters = getServiceCounters(
                      counters,
                      serviceId
                    );

                    F({
                      ...form,
                      service_id: serviceId,
                      counter_id: String(
                        matchingCounters[0]?.id || ''
                      )
                    });
                  }}
                >
                  <option value="">Select a service</option>

                  {services.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>

                {!services.length && (
                  <small>No services available. Check backend.</small>
                )}
              </label>

              <label>
                Counter / Room

                <select
                  required
                  value={form.counter_id}
                  onChange={e =>
                    F({ ...form, counter_id: e.target.value })
                  }
                >
                  <option value="">Select a counter</option>

                  {availableCounters.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>

                {!availableCounters.length && (
                  <small>
                    No counter available for this service.
                  </small>
                )}
              </label>

              <button
                className="primary"
                type="submit"
                disabled={!services.length || !availableCounters.length}
              >
                Generate Token
              </button>
            </form>

            {mine && (
              <div className="ticket">
                <small>YOUR TOKEN</small>
                <strong>{mine.token_number}</strong>

                <div>
                  Queue position: {mine.position}
                  {' · '}
                  Estimated wait: {mine.estimated_wait_minutes} min
                </div>

                <b>{mine.counter_name}</b>
              </div>
            )}
          </section>
        )}

        {/* STAFF DASHBOARD */}
        {page === 'staff' && (
          <>
            <div className="hero">
              <div>
                <small>RECEPTION CONTROL PANEL</small>
                <h2>Patient Queue Overview</h2>
                <p>
                  Staff can monitor patient tokens and their current status.
                  Patient completion is controlled by the doctor.
                </p>
              </div>

              <button onClick={load}>
                <RefreshCw size={15} /> Refresh
              </button>
            </div>

            <div className="cards">
              {counters.map(c => {
                const roomQueue = queue.filter(
                  t => Number(t.counter_id) === Number(c.id)
                );

                const current = roomQueue.find(
                  t => t.status === 'serving'
                );

                const waiting = roomQueue.filter(
                  t => t.status === 'waiting'
                );

                return (
                  <section className="counter" key={c.id}>
                    <small>COUNTER / ROOM</small>
                    <h3>{c.name}</h3>

                    <div className="current-patient">
                      <small>CURRENTLY SERVING</small>

                      {current ? (
                        <>
                          <h2>{current.token_number}</h2>
                          <h3>{current.customer_name}</h3>
                          <span className="live">● SERVING</span>
                        </>
                      ) : (
                        <p>No active patient.</p>
                      )}
                    </div>

                    <hr />

                    <h3>
                      Waiting Patients ({waiting.length})
                    </h3>

                    {roomQueue.length > 0 ? (
                      roomQueue.map(t => (
                        <div className="action" key={t.id}>
                          <span>
                            <b>{t.token_number}</b>
                            <small>{t.customer_name}</small>
                          </span>

                          <span>
                            {t.status === 'serving' ? (
                              <span className="live">Serving</span>
                            ) : (
                              <small>Waiting</small>
                            )}
                          </span>
                        </div>
                      ))
                    ) : (
                      <p>No patients in this queue.</p>
                    )}
                  </section>
                );
              })}

              {!counters.length && (
                <p>No active counters found.</p>
              )}
            </div>
          </>
        )}

        {/* DOCTOR DASHBOARD */}
        {page === 'doctor' && (
          <>
            <div className="hero">
              <div>
                <small>DOCTOR CONTROL PANEL</small>
                <h2>Doctor Dashboard</h2>
                <p>
                  Complete the current patient and automatically call the next patient.
                </p>
              </div>

              <button onClick={load}>
                <RefreshCw size={15} /> Refresh
              </button>
            </div>

            {counters.length === 0 ? (
              <section>
                <h3>No rooms or counters found</h3>
                <p>
                  Please check whether your backend has active counters.
                </p>
              </section>
            ) : (
              <div className="doctor-grid">
                {counters.map(c => {
                  const roomQueue = queue.filter(
                    t => Number(t.counter_id) === Number(c.id)
                  );

                  const current = roomQueue.find(
                    t => t.status === 'serving'
                  );

                  const waiting = roomQueue
                    .filter(t => t.status === 'waiting')
                    .sort(
                      (a, b) =>
                        new Date(a.created_at) -
                        new Date(b.created_at)
                    );

                  const next = waiting[0];

                  return (
                    <section className="doctor-card" key={c.id}>

                      <div className="doctor-heading">
                        <div>
                          <small>DOCTOR / ROOM</small>
                          <h3>{c.name}</h3>
                        </div>

                        <span className="live">● LIVE</span>
                      </div>

                      <hr />

                      <div className="current-patient">
                        <small>CURRENT PATIENT</small>

                        {current ? (
                          <>
                            <h2>{current.token_number}</h2>
                            <h3>{current.customer_name}</h3>
                            <p>Currently being served</p>

                            <div className="patient-actions">
                              <button
                                onClick={() =>
                                  act(`/api/tokens/${current.id}/recall`)
                                }
                              >
                                <Volume2 size={15} />
                                Recall
                              </button>

                              <button
                                className="primary"
                                onClick={() =>
                                  act(
                                    `/api/counters/${c.id}/complete-and-next`
                                  )
                                }
                              >
                                <CheckCircle size={15} />
                                Complete & Call Next
                              </button>

                              <button
                                onClick={() =>
                                  act(`/api/tokens/${current.id}/skip`)
                                }
                              >
                                <SkipForward size={15} />
                                Skip
                              </button>
                            </div>
                          </>
                        ) : (
                          <div className="empty-patient">
                            <h3>No active patient</h3>
                            <p>Call the next patient to begin.</p>
                          </div>
                        )}
                      </div>

                      <hr />

                      <div className="next-patient">
                        <small>NEXT PATIENT</small>

                        {next ? (
                          <>
                            <h2>{next.token_number}</h2>
                            <h3>{next.customer_name}</h3>

                            <button
                              className="primary call-next-btn"
                              disabled={!!current}
                              onClick={() =>
                                act(`/api/counters/${c.id}/next`)
                              }
                            >
                              <PhoneCall size={16} />
                              Call Next Patient
                            </button>
                          </>
                        ) : (
                          <p>No waiting patients.</p>
                        )}
                      </div>

                      <hr />

                      <div className="waiting-list">
                        <h3>
                          Waiting Patients ({waiting.length})
                        </h3>

                        {waiting.length > 0 ? (
                          waiting.map((t, index) => (
                            <div className="waiting-patient" key={t.id}>
                              <div>
                                <b>{t.token_number}</b>
                                <small>{t.customer_name}</small>
                              </div>

                              <span>#{index + 1}</span>
                            </div>
                          ))
                        ) : (
                          <p>No patients in queue.</p>
                        )}
                      </div>
                    </section>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* DISPLAY SCREEN */}
        {page === 'display' && (
          <section className="display">
            <div className="displaytop">
              <div>
                <small>PUBLIC WAITING ROOM SCREEN</small>
                <h2>Now Calling</h2>
              </div>

              <select
                value={lang}
                onChange={e => G(e.target.value)}
              >
                <option value="bn">বাংলা Voice</option>
                <option value="en">English Voice</option>
              </select>
            </div>

            <div className="screen">
              <small>QUEUELESS BD · SMART QUEUE</small>
              <label>NOW CALLING</label>

              <strong>
                {last?.token_number ||
                  queue.find(t => t.status === 'serving')?.token_number ||
                  '— — —'}
              </strong>

              <h3>
                {last?.customer_name ||
                  queue.find(t => t.status === 'serving')?.customer_name ||
                  'Waiting for next patient'}
              </h3>

              <p>
                {last?.counter_name ||
                  queue.find(t => t.status === 'serving')?.counter_name ||
                  ''}
              </p>

              <div className="next">
                NEXT:{' '}

                {queue
                  .filter(t => t.status === 'waiting')
                  .slice(0, 5)
                  .map(t => t.token_number)
                  .join(' · ') || 'No waiting tokens'}
              </div>

              <button
                onClick={() => {
                  const t =
                    last ||
                    queue.find(x => x.status === 'serving');

                  if (t) {
                    lastAnnounced.current = '';
                    announce(t);
                  }
                }}
              >
                <Volume2 size={17} />
                Repeat Voice Announcement
              </button>
            </div>

            <p className="hint">
              Keep this page open on a TV or monitor.
              Voice uses the browser/device speech engine.
              Bangla voice depends on installed voices.
            </p>
          </section>
        )}

        {/* FOOTER */}
        <footer>
          QueueLess BD
          <span>
            AI-powered queue & automated token calling
          </span>
        </footer>

      </main>
    </div>
  );
}

// QUEUE TABLE
function Queue({ rows }) {
  return (
    <div className="tablewrap">
      <table>
        <thead>
          <tr>
            <th>Token</th>
            <th>Name</th>
            <th>Counter</th>
            <th>Status</th>
            <th>Est. Wait</th>
          </tr>
        </thead>

        <tbody>
          {rows.map(t => (
            <tr key={t.id}>
              <td>{t.token_number}</td>
              <td>{t.customer_name}</td>
              <td>{t.counter_name}</td>
              <td>{t.status}</td>
              <td>{t.estimated_wait_minutes} min</td>
            </tr>
          ))}

          {!rows.length && (
            <tr>
              <td colSpan="5">
                No tokens yet. Book a token to begin.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
