from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Ellipse

BASE_DIR = Path(__file__).resolve().parents[1]          # dossier backend/
PROJECT_DIR = BASE_DIR.parent                            # racine du projet
FIG_DIR = PROJECT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def add_box(ax, xy, w, h, text, fontsize=10):
    rect = Rectangle(xy, w, h, fill=False, linewidth=1.5)
    ax.add_patch(rect)
    ax.text(xy[0] + w/2, xy[1] + h/2, text, ha='center', va='center', fontsize=fontsize, wrap=True)


def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle='->', mutation_scale=15, linewidth=1.2))

# Architecture
fig, ax = plt.subplots(figsize=(11, 6))
ax.axis('off')
add_box(ax, (0.5, 3.8), 2.2, 1.0, 'Plateforme e-learning\nTEACHIUM / LMS')
add_box(ax, (4.0, 3.8), 2.2, 1.0, 'API REST\nFastAPI')
add_box(ax, (7.5, 4.6), 2.5, 0.8, 'Profilage IA\nK-Means + Decision Tree')
add_box(ax, (7.5, 3.4), 2.5, 0.8, 'Moteur de\nrecommandation')
add_box(ax, (7.5, 2.2), 2.5, 0.8, 'Assistant\nconversationnel')
add_box(ax, (4.0, 1.4), 2.2, 1.0, 'Base de données / CSV\nApprenants')
add_box(ax, (0.5, 1.4), 2.2, 1.0, 'Dashboard\nStreamlit')
arrow(ax, (2.7, 4.3), (4.0, 4.3))
arrow(ax, (6.2, 4.3), (7.5, 5.0))
arrow(ax, (6.2, 4.1), (7.5, 3.8))
arrow(ax, (6.2, 3.9), (7.5, 2.6))
arrow(ax, (5.1, 3.8), (5.1, 2.4))
arrow(ax, (4.0, 1.9), (2.7, 1.9))
ax.set_xlim(0, 10.5); ax.set_ylim(0.8, 5.8)
plt.tight_layout()
plt.savefig(FIG_DIR / 'architecture_systeme.png', dpi=160)
plt.close()

# Use case
fig, ax = plt.subplots(figsize=(10, 6))
ax.axis('off')
# actors
ax.text(0.6, 4.7, 'Apprenant', ha='center', fontsize=10)
ax.plot([0.6,0.6],[3.5,4.3], color='black')
ax.plot([0.3,0.9],[4.0,4.0], color='black')
ax.plot([0.6,0.3],[3.5,3.0], color='black')
ax.plot([0.6,0.9],[3.5,3.0], color='black')
ax.add_patch(plt.Circle((0.6,4.55),0.15, fill=False))
ax.text(0.6, 2.2, 'Formateur', ha='center', fontsize=10)
ax.plot([0.6,0.6],[1.0,1.8], color='black')
ax.plot([0.3,0.9],[1.5,1.5], color='black')
ax.plot([0.6,0.3],[1.0,0.5], color='black')
ax.plot([0.6,0.9],[1.0,0.5], color='black')
ax.add_patch(plt.Circle((0.6,2.05),0.15, fill=False))
# system boundary
add_box(ax, (2.2, 0.5), 7.2, 4.8, 'Système de tutorat intelligent TEACHIUM', fontsize=12)
# ellipses
cases = [
    ((3.0,4.3),'Consulter\nprofil'),
    ((5.2,4.3),'Recevoir\nrecommandation'),
    ((7.4,4.3),'Poser question\nau chatbot'),
    ((3.3,2.2),'Suivre\nprogression'),
    ((5.6,2.2),'Consulter\ndashboard'),
    ((7.7,2.2),'Évaluer\nperformances'),
]
for (x,y),txt in cases:
    e=Ellipse((x,y),1.8,0.7,fill=False,linewidth=1.3)
    ax.add_patch(e); ax.text(x,y,txt,ha='center',va='center',fontsize=9)
# lines
for x,y in [(3,4.3),(5.2,4.3),(7.4,4.3),(3.3,2.2)]: ax.plot([0.9,x-0.9],[4.0,y],color='black',linewidth=.8)
for x,y in [(5.6,2.2),(7.7,2.2),(3.3,2.2)]: ax.plot([0.9,x-0.9],[1.5,y],color='black',linewidth=.8)
ax.set_xlim(0,10); ax.set_ylim(0,6)
plt.tight_layout()
plt.savefig(FIG_DIR / 'diagramme_cas_utilisation.png', dpi=160)
plt.close()

# Class diagram simple
fig, ax = plt.subplots(figsize=(12, 7))
ax.axis('off')
def class_box(x,y,w,h,title,attrs,methods):
    ax.add_patch(Rectangle((x,y),w,h,fill=False,linewidth=1.4))
    ax.plot([x,x+w],[y+h-0.45,y+h-0.45], color='black')
    ax.plot([x,x+w],[y+h-1.6,y+h-1.6], color='black')
    ax.text(x+w/2,y+h-0.25,title,ha='center',va='center',fontsize=10,fontweight='bold')
    ax.text(x+0.1,y+h-0.65,'\n'.join(attrs),ha='left',va='top',fontsize=8)
    ax.text(x+0.1,y+h-1.8,'\n'.join(methods),ha='left',va='top',fontsize=8)
class_box(0.4,4.0,2.6,2.3,'Learner',['student_id','average_score','completion_rate','failed_quizzes'],['get_profile()'])
class_box(4.2,4.0,2.6,2.3,'ProfileModel',['features','classifier','scaler'],['predict_profile()','predict_cluster()'])
class_box(7.9,4.0,2.8,2.3,'RecommendationEngine',['rules','content_catalog'],['recommend_content()'])
class_box(4.2,1.0,2.6,2.3,'ChatbotService',['question','profile'],['generate_answer()'])
class_box(0.4,1.0,2.6,2.3,'DashboardService',['learners','metrics'],['get_stats()'])
class_box(7.9,1.0,2.8,2.3,'FastAPIController',['routes','schemas'],['profile_analyze()','recommendations()','chatbot_ask()'])
arrow(ax,(3.0,5.1),(4.2,5.1)); arrow(ax,(6.8,5.1),(7.9,5.1)); arrow(ax,(9.3,4.0),(9.3,3.3)); arrow(ax,(7.9,2.2),(6.8,2.2)); arrow(ax,(4.2,2.2),(3.0,2.2))
ax.set_xlim(0,11.2); ax.set_ylim(0.5,6.7)
plt.tight_layout()
plt.savefig(FIG_DIR / 'diagramme_classes.png', dpi=160)
plt.close()

print('Diagrammes générés dans figures/')
