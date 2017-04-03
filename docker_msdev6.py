"""Builder for old Msdev6 projects, using Docker."""
import os
import re
import time
from buildsystem.builder import Builder, task
from subprocess import CalledProcessError

class DockerMsdev6(Builder):
    """MSDev6 docker powered builder definition. You definitely must set the
    docker_volume `c:\\code`!"""
    recursive = True
    project_extension = '.dsp'
    root_dirs = os.path.dirname(os.path.realpath(__file__))
    exclude = []
    projects = []
    docker_volumes = {}
    include_dirs = []
    lib_dirs = []
    full_rebuild = False

    @task('collect-projects')
    def collect_projects(self):
        """Walks recursively through the `root_dir` and finds all files
        that ends with `project_extension`."""
        for root_dir in self.root_dirs:
            for root, _, files in os.walk(root_dir):
                for file in files:
                    if file[-4:].lower() == self.project_extension:
                        if file.lower() not in [s.lower() for s in self.exclude]:
                            self.projects.append(os.path.join(root, file))

    @task('start-docker')
    def start_docker(self):
        output = self.run(['docker', 'ps', '-aq', '--filter', 'name=backendbuilder'])
        if output != b'':
            cmd = ['docker', 'start', 'backendbuilder']
        else:
            cmd = ['docker', 'run', '--name', 'backendbuilder', '-d']
            for key, val in self.docker_volumes:
                cmd.append('%s:%s' % (val, key))
            cmd = cmd + ['msdev', 'ping', '-t', 'localhost']
        self.run(cmd)

    @task('compile')
    def compile(self):
        for prj in self.projects:
            dsp_file = os.path.basename(prj)
            folder = os.path.dirname(prj)
            target = dsp_file.split('.')[0] + ' - Win32 Release'

            cmd = ['docker', 'exec',
                   '-e', 'ADDITIONAL_INCLUDES=%s' % ';'.join(self.include_dirs),
                   '-e', 'ADDITIONAL_LIBS=%s' % ';'.join(self.lib_dirs),
                   'backendbuilder', 'c:\\entrypoint.bat', 'msdev',
                   os.path.join(folder, dsp_file)
                   .replace(self.docker_volumes['C:\\code'] + '\\', ''),
                   '/MAKE', target, '/REBUILD' if self.full_rebuild else '/BUILD', '/USEENV']
            result = self.run_msdev_and_validate_output(cmd)

            if result[0] > 0:
                self.output('\n      %s ... %s Fehler, %s Warnung(en)' %
                            (dsp_file.split('.')[0], result[0], result[1]), err=True)
                self.log('compile', result[2])
            elif result[1] > 0:
                self.output('\n      %s ... %s Fehler, %s Warnung(en)' %
                            (dsp_file.split('.')[0], result[0], result[1]), warn=True)
            else:
                self.output('\n      %s ... 0 Fehler, 0 Warnung(en)' % dsp_file.split('.')[0],
                            ok=True)

    def log(self, task_name, what):
        if 'log_enabled' in dir(self) and self.log_enabled:
            with open(self.logpath, 'a', encoding='iso-8859-1') as file:
                file.write('%s :: [%s] :: %s\n' %
                           (str(int((time.time() - self.starttime) * 1000)), task_name, what,))

    def run_msdev_and_validate_output(self, command):
        """Runs msdev command and validates its output. It returns a tuple with three
        values, the first one is the number of errors, the second one the number of
        warnings during compilation. The third tuple entry is the whole output string,
        if you want to log it."""

        try:
            out = self.run(command).decode("iso-8859-1")
        except CalledProcessError as exc:
            out = exc.output.decode('iso-8859-1')

        errors = re.search('([0-9]+) Fehler', out)
        warnings = re.search('([0-9]+) Warnung(en)', out)

        num_errors, num_warnings = 0, 0
        if errors is not None:
            num_errors = int(errors.group(1))
        if warnings is not None:
            num_warnings = int(warnings.group(1))

        return (num_errors, num_warnings, out)

    @task('stop-docker')
    def stop_docker(self):
        self.run(['docker', 'stop', 'backendbuilder'])

if __name__ == '__main__':
    builder = DockerMsdev6()
    builder.conf(exclude=('VS7DEMO.dsp', 'V7DPM.dsp', 'V7WSNAPC.dsp', 'V7WSNAPD.dsp',
                          'V7WSNAPE.dsp', 'V7RTAPPX.DSP', 'V7RTSOPX.DSP', 'V7RTSVSX.DSP',
                          'V7PRDEMX.DSP', 'V7PRSVCX.DSP'),
                 root_dirs=('K:/VISION7/AUFTR', 'K:/VISION7/COMP', 'K:/VISION7/ERROR',
                            'K:/VISION7/GRAB', 'K:/VISION7/KOMM', 'K:/VISION7/MEM',
                            'K:/VISION7/Overlay', 'K:/VISION7/PE', 'PEUTILS', 'K:/VISION7/STEU',
                            'K:/VISION7/V7PRAPPX'),
                 docker_volumes={
                     'C:\\code': 'D:\\SWE\\Git\\SIMAVIS P\\Backend',
                     'c:\\inc': 'D:\\SWE\\Git\\INC',
                     'c:\\lib': 'D:\\SWE\\Git\\Lib\\VC++',
                     'c:\\vision7\\inc': 'D:\\SWE\\Git\\SIMAVIS P\\Backend\\Vision7\\INC',
                     'c:\\vision7\\lib': 'D:\\SWE\\Git\\SIMAVIS P\\Backend\\Vision7\\LIB'
                 },
                 include_dirs=['C:\\inc\\halcon12.0', 'c:\\inc\\halcon12.0\\cpp',
                               'c:\\code\\glob\\inc'],
                 lib_dirs=['C:\\LIB\\halcon12.0\\x86sse2-win32', 'c:\\code\\glob\\lib'],
                 log_enabled=True)
    builder.build()
