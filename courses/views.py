from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.base import TemplateResponseMixin, View
from django.contrib.auth.mixins import LoginRequiredMixin,\
                                        PermissionRequiredMixin
from django.forms.models import modelform_factory
from django.apps import apps
from django.db.models import Count

from braces.views import CsrfExemptMixin, JsonRequestResponseMixin

from .models import Course, Module, Content, Subject
from .forms import ModuleFormSet
from students.forms import CourseEnrollForm


# class ManageCourseList(ListView):
#     """Manage course list for public display"""

#     model = Course
#     template_name = 'courses/manage/course/list.html'

#     def get_queryset(self):
#         qs = super(ManageCourseList, self).get_queryset()

#         return qs.filter(owner=self.request.user)


class OwnerMixin(object):
    """Mixin for filtering objects by user"""

    def get_queryset(self):
        qs = super(OwnerMixin, self).get_queryset()

        return qs.filter(owner=self.request.user)


class OwnerEditMixin(object):
    """
    Mixin for form validation checking
    (form_valid method will perform on createview, updateview)
     and user asigning
    """

    def form_valid(self, form):
        form.instance.owner = self.request.user

        return super(OwnerEditMixin, self).form_valid(form)


class OwnerCourseMixin(OwnerMixin, LoginRequiredMixin):
    """OwnerCourse list display mixins"""

    model = Course
    fields = ['subject', 'title', 'slug', 'overview']
    success_url = reverse_lazy('manage_course_list')


class OwnerCourseEditMixin(OwnerCourseMixin, OwnerEditMixin):
    """Owner corse edit mixins"""

    fields = ['subject', 'title', 'slug', 'overview']
    template_name = 'courses/manage/course/form.html'
    success_url = reverse_lazy(('manage_course_list'))


class ManageCourseListView(OwnerCourseMixin, ListView):
    """Owner Course Display List"""

    template_name = 'courses/manage/course/list.html'


class CourseCreateView(PermissionRequiredMixin,
                       OwnerCourseEditMixin,
                       CreateView):
    """Owner Course Create"""

    permission_required = 'courses.add_course'


class CourseUpdateView(OwnerCourseEditMixin, UpdateView):
    """Owner Course Update View"""

    permission_required = 'courses.change_course'


class CourseDeleteView(OwnerCourseMixin, DeleteView):
    """Owner Course Delete View"""

    template_name = 'courses/manage/course/delete.html'
    success_url = reverse_lazy('manage_course_list')
    permission_required = 'courses.delete_course'


class CourseModuleUpdateView(TemplateResponseMixin, View):
    """New module add, update, delete view"""

    template_name = 'courses/manage/module/formset.html'
    course = None

    def get_formset(self, data=None):

        return ModuleFormSet(instance=self.course, data=data)

    def dispatch(self, request, pk):
        self.course = get_object_or_404(Course, id=pk,
                                        owner=self.request.user)

        return super(CourseModuleUpdateView, self).dispatch(request, pk)

    def get(self, request, *args, **kwargs):
        formset = self.get_formset()

        return self.render_to_response({'course': self.course,
                                        'formset': formset})

    def post(self, request, *args, **kwargs):
        formset = self.get_formset(data=request.POST)
        if formset.is_valid():
            formset.save()

            return redirect('manage_course_list')
        return self.render_to_response({'course': self.course,
                                        'formset': formset})


class ContentCreateUpdateView(TemplateResponseMixin, View):
    """add and update various content"""

    module = None
    model = None
    obj = None
    template_name = 'courses/manage/content/form.html'

    def get_model(self, model_name):

        if model_name in ['text', 'video', 'image', 'file']:
            return apps.get_model(app_label='courses',
                                  model_name=model_name)
        return None

    def get_form(self, model, *args, **kwargs):
        Form = modelform_factory(model, exclude=['owner',
                                                 'order',
                                                 'created',
                                                 'updated'])
        return Form(*args, **kwargs)

    def dispatch(self, request, module_id, model_name, id=None):
        self.module = get_object_or_404(Module,
                                        id=module_id,
                                        course__owner=request.user)
        self.model = self.get_model(model_name)
        if id:
            self.obj = get_object_or_404(self.model, id=id, owner=request.user)

        return super(ContentCreateUpdateView, self).dispatch(request,
                                                             module_id,
                                                             model_name,
                                                             id)

    def get(self, request, module_id, model_name, id=None):
        form = self.get_form(self.model, instance=self.obj)

        return self.render_to_response({'form': form, 'object': self.obj})

    def post(self, request, module_id, model_name, id=None):
        form = self.get_form(self.model, instance=self.obj,
                             data=request.POST, files=request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.save()

            if not id:
                Content.objects.create(module=self.module, item=obj)

            return redirect('module_content_list', self.module.id)

        return self.render_to_response({'form': form, 'object': self.obj})


class ContentDeleteView(View):
    """Delete Contents"""

    def post(self, request, id):
        content = get_object_or_404(Content, id=id,
                                    module__course__owner=request.user)
        content.item.delete()
        content.delete()

        return redirect('module_content_list', module.id)


class ModuleContentListView(TemplateResponseMixin, View):
    """List of all content in a module"""

    template_name = 'courses/manage/module/content_list.html'

    def get(self, request, module_id):
        module = get_object_or_404(Module, id=module_id,
                                   course__owner=request.user)

        return self.render_to_response({'module': module})


class ModuleOrderView(CsrfExemptMixin, JsonRequestResponseMixin, View):
    """ordering the module by ajax action"""

    def post(self, request):
        for id, order in self.request_json.items():
            Module.objects.filter(id=id, course__owner=request.user)\
                                    .update(order=order)

        return self.render_json_response({'saved': 'OK'})


class ContentOrderView(CsrfExemptMixin, JsonRequestResponseMixin, View):
    """ordering the contents by ajax action"""

    def post(self, request):
        for id, order in self.request_json.items():
            Content.objects.filter(id=id, module__course__owner=request.user)\
                                    .update(order=order)

        return self.render_json_response({'saved': 'OK'})


class CourseListView(TemplateResponseMixin, View):
    """Course display for public view"""

    model = Course
    template_name = 'courses/course/list.html'

    def get(self, request, subject=None):
        subjects = Subject.objects.annotate(total_courses=Count('courses'))
        courses = Course.objects.annotate(total_modules=Count('modules'))

        if subject:
            subject = get_object_or_404(Subject, slug=subject)
            courses = courses.filter(subject=subject)
        return self.render_to_response({'subjects': subjects,
                                       'subject': subject,
                                       'courses': courses})


class CourseDetailView(DetailView):
    """Enrolled Course Detail View"""

    model = Course
    template_name = 'courses/course/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["enroll_form"] = CourseEnrollForm(
                                initial={'course': self.object})

        return context
