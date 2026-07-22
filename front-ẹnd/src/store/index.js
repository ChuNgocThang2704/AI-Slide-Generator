import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      pendingEmail: null,

      login: (user, token, refreshToken = null) =>
        set({ user, token, refreshToken, isAuthenticated: true, pendingEmail: null }),
      logout: () => set({ user: null, token: null, refreshToken: null, isAuthenticated: false, pendingEmail: null }),
      setPendingEmail: (email) => set({ pendingEmail: email }),
      clearPendingEmail: () => set({ pendingEmail: null }),
      updateUser: (updates) =>
        set((state) => ({ user: { ...state.user, ...updates } })),
    }),
    {
      name: 'auth-storage',
    }
  )
);

export const usePresentationStore = create(
  persist(
    (set, get) => ({
      presentations: [],
      currentPresentation: null,

      setPresentations: (presentations) => set({ presentations }),
      setCurrentPresentation: (pres) => set({ currentPresentation: pres }),

      addPresentation: (pres) =>
        set((state) => ({
          presentations: [pres, ...state.presentations],
        })),

      updatePresentation: (id, updates) =>
        set((state) => ({
          presentations: state.presentations.map((p) =>
            p.id === id ? { ...p, ...updates } : p
          ),
          currentPresentation:
            state.currentPresentation?.id === id
              ? { ...state.currentPresentation, ...updates }
              : state.currentPresentation,
        })),

      deletePresentation: (id) =>
        set((state) => ({
          presentations: state.presentations.filter((p) => p.id !== id),
        })),

      updateSlide: (presId, slideIndex, updates) =>
        set((state) => {
          const pres = state.currentPresentation;
          if (!pres || pres.id !== presId) return state;
          const newSlides = [...pres.slides];
          newSlides[slideIndex] = { ...newSlides[slideIndex], ...updates };
          const updatedPres = { ...pres, slides: newSlides };
          return {
            currentPresentation: updatedPres,
            presentations: state.presentations.map((p) =>
              p.id === presId ? updatedPres : p
            ),
          };
        }),
    }),
    {
      name: 'presentations-storage',
    }
  )
);

export const useUIStore = create((set) => ({
  toasts: [],
  addToast: (message, type = 'info') => {
    const id = Date.now();
    set((state) => ({ toasts: [...state.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }));
    }, 3500);
  },
  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

// ─────────────────────────────────────────────
// PROJECT STORE (From API)
// ─────────────────────────────────────────────
export const useProjectStore = create(
  persist(
    (set, get) => ({
      projects: [],
      currentProject: null,
      projectsPage: { content: [], totalElements: 0, totalPages: 0 },

      setProjects: (projects) => set({ projects }),
      setProjectsPage: (page) => set({ projectsPage: page }),
      setCurrentProject: (project) => set({ currentProject: project }),

      addProject: (project) =>
        set((state) => ({
          projects: [project, ...state.projects],
        })),

      updateProject: (id, updates) =>
        set((state) => ({
          projects: state.projects.map((p) =>
            p.id === id ? { ...p, ...updates } : p
          ),
          currentProject:
            state.currentProject?.id === id
              ? { ...state.currentProject, ...updates }
              : state.currentProject,
        })),

      deleteProject: (id) =>
        set((state) => ({
          projects: state.projects.filter((p) => p.id !== id),
          currentProject: state.currentProject?.id === id ? null : state.currentProject,
        })),

      deleteMultipleProjects: (ids) =>
        set((state) => ({
          projects: state.projects.filter((p) => !ids.includes(p.id)),
        })),

      updateSlidePages: (projectId, pages) =>
        set((state) => ({
          currentProject:
            state.currentProject?.id === projectId
              ? { ...state.currentProject, pages }
              : state.currentProject,
        })),
    }),
    {
      name: 'projects-storage',
    }
  )
);

// ─────────────────────────────────────────────
// DOCUMENT STORE (From API)
// ─────────────────────────────────────────────
export const useDocumentStore = create(
  persist(
    (set, get) => ({
      documents: [],
      currentDocument: null,
      documentsPage: { content: [], totalElements: 0, totalPages: 0 },

      setDocuments: (documents) => set({ documents }),
      setDocumentsPage: (page) => set({ documentsPage: page }),
      setCurrentDocument: (document) => set({ currentDocument: document }),

      addDocument: (document) =>
        set((state) => ({
          documents: [document, ...state.documents],
        })),

      updateDocument: (id, updates) =>
        set((state) => ({
          documents: state.documents.map((d) =>
            d.id === id ? { ...d, ...updates } : d
          ),
          currentDocument:
            state.currentDocument?.id === id
              ? { ...state.currentDocument, ...updates }
              : state.currentDocument,
        })),

      deleteDocument: (id) =>
        set((state) => ({
          documents: state.documents.filter((d) => d.id !== id),
          currentDocument: state.currentDocument?.id === id ? null : state.currentDocument,
        })),

      deleteMultipleDocuments: (ids) =>
        set((state) => ({
          documents: state.documents.filter((d) => !ids.includes(d.id)),
        })),
    }),
    {
      name: 'documents-storage',
    }
  )
);
