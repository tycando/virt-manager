#
# List of OS Specific data
#
# Copyright 2006-2008, 2013-2014 Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.

import datetime
import re

from gi.repository import Libosinfo as libosinfo


###################
# Sorting helpers #
###################

def _remove_older_point_releases(distro_list):
    ret = distro_list[:]

    def _get_minor_version(osobj):
        return int(osobj.name.rsplit(".", 1)[-1])

    def _find_latest(prefix):
        """
        Given a prefix like 'rhel4', find the latest 'rhel4.X',
        and remove the rest from the os list
        """
        latest_os = None
        first_id = None
        for osobj in ret[:]:
            if not re.match("%s\.\d+" % prefix, osobj.name):
                continue

            if first_id is None:
                first_id = ret.index(osobj)
            ret.remove(osobj)

            if (latest_os and
                _get_minor_version(latest_os) > _get_minor_version(osobj)):
                continue
            latest_os = osobj

        if latest_os:
            ret.insert(first_id, latest_os)

    _find_latest("rhel4")
    _find_latest("rhel5")
    _find_latest("rhel6")
    _find_latest("rhel7")
    _find_latest("freebsd9")
    _find_latest("freebsd10")
    return ret


def _sort(tosort, sortpref=None, limit_point_releases=False):
    sortby_mappings = {}
    distro_mappings = {}
    retlist = []
    sortpref = sortpref or []

    # Make sure we are sorting by 'sortby' if specified, and group distros
    # by their 'distro' tag first and foremost
    for key, osinfo in tosort.items():
        sortby = osinfo.sortby or key
        # Hack to allow "sortby" duplicates.  Remove when this never happens
        # with libosinfo
        while sortby_mappings.get(sortby):
            sortby = sortby + ".1"
        sortby_mappings[sortby] = key

        distro = osinfo.urldistro or "zzzzzzz"
        if distro not in distro_mappings:
            distro_mappings[distro] = []
        distro_mappings[distro].append(sortby)

    # We want returned lists to be sorted descending by 'distro', so we get
    # debian5, debian4, fedora14, fedora13
    #   rather than
    # debian4, debian5, fedora13, fedora14
    for distro_list in distro_mappings.values():
        distro_list.sort()
        distro_list.reverse()

    sorted_distro_list = distro_mappings.keys()
    sorted_distro_list.sort()
    sortpref.reverse()
    for prefer in sortpref:
        if prefer not in sorted_distro_list:
            continue
        sorted_distro_list.remove(prefer)
        sorted_distro_list.insert(0, prefer)

    for distro in sorted_distro_list:
        distro_list = distro_mappings[distro]
        for key in distro_list:
            orig_key = sortby_mappings[key]
            retlist.append(tosort[orig_key])

    if limit_point_releases:
        retlist = _remove_older_point_releases(retlist)

    return retlist


class _OSDB(object):
    """
    Entry point for the public API
    """
    def __init__(self):
        self.__os_loader = None
        self.__all_variants = None

    # This is only for back compatibility with pre-libosinfo support.
    # This should never change.
    _aliases = {
        "altlinux" : "altlinux1.0",
        "debianetch" : "debian4",
        "debianlenny" : "debian5",
        "debiansqueeze" : "debian6",
        "debianwheezy" : "debian7",
        "freebsd10" : "freebsd10.0",
        "freebsd6" : "freebsd6.0",
        "freebsd7" : "freebsd7.0",
        "freebsd8" : "freebsd8.0",
        "freebsd9" : "freebsd9.0",
        "mandriva2009" : "mandriva2009.0",
        "mandriva2010" : "mandriva2010.0",
        "mbs1" : "mbs1.0",
        "msdos" : "msdos6.22",
        "openbsd4" : "openbsd4.2",
        "opensolaris" : "opensolaris2009.06",
        "opensuse11" : "opensuse11.4",
        "opensuse12" : "opensuse12.3",
        "rhel4" : "rhel4.0",
        "rhel5" : "rhel5.0",
        "rhel6" : "rhel6.0",
        "rhel7" : "rhel7.0",
        "ubuntuhardy" : "ubuntu8.04",
        "ubuntuintrepid" : "ubuntu8.10",
        "ubuntujaunty" : "ubuntu9.04",
        "ubuntukarmic" : "ubuntu9.10",
        "ubuntulucid" : "ubuntu10.04",
        "ubuntumaverick" : "ubuntu10.10",
        "ubuntunatty" : "ubuntu11.04",
        "ubuntuoneiric" : "ubuntu11.10",
        "ubuntuprecise" : "ubuntu12.04",
        "ubuntuquantal" : "ubuntu12.10",
        "ubunturaring" : "ubuntu13.04",
        "ubuntusaucy" : "ubuntu13.10",
        "virtio26": "fedora10",
        "vista" : "winvista",
        "winxp64" : "winxp",

        # Old --os-type values
        "linux" : "generic",
        "windows" : "winxp",
        "solaris" : "solaris10",
        "unix": "freebsd9",
        "other": "generic",
    }


    #################
    # Internal APIs #
    #################

    def _make_default_variants(self):
        ret = {}

        # Generic variant
        v = _OsVariant(None)
        ret[v.name] = v
        return ret

    @property
    def _os_loader(self):
        if not self.__os_loader:
            loader = libosinfo.Loader()
            loader.process_default_path()

            self.__os_loader = loader
        return self.__os_loader

    @property
    def _all_variants(self):
        if not self.__all_variants:
            loader = self._os_loader
            allvariants = self._make_default_variants()
            db = loader.get_db()
            oslist = db.get_os_list()
            for os in range(oslist.get_length()):
                osi = _OsVariant(oslist.get_nth(os))
                allvariants[osi.name] = osi

            self.__all_variants = allvariants
        return self.__all_variants


    ###############
    # Public APIs #
    ###############

    def lookup_os(self, key):
        key = self._aliases.get(key) or key
        ret = self._all_variants.get(key)
        if ret is None:
            return None
        return ret

    def lookup_os_by_media(self, location):
        media = libosinfo.Media.create_from_location(location, None)
        ret = self._os_loader.get_db().guess_os_from_media(media)
        if ret and len(ret) > 0 and ret[0]:
            return ret[0].get_short_id()
        return None

    def list_types(self):
        approved_types = ["linux", "windows", "unix",
            "solaris", "other", "generic"]
        return approved_types

    def list_os(self, typename=None, only_supported=False, sortpref=None):
        sortmap = {}

        for key, osinfo in self._all_variants.items():
            if typename and typename != osinfo.get_typename():
                continue
            if only_supported and not osinfo.supported:
                continue
            sortmap[key] = osinfo

        return _sort(sortmap, sortpref=sortpref,
            limit_point_releases=only_supported)


#####################
# OsVariant classes #
#####################

def _is_os_related_to(o, related_os_list):
    if o.get_short_id() in related_os_list:
        return True
    related = o.get_related(libosinfo.ProductRelationship.DERIVES_FROM)
    clones = o.get_related(libosinfo.ProductRelationship.CLONES)
    for r in related.get_elements() + clones.get_elements():
        if (r.get_short_id() in related_os_list or
            _is_os_related_to(r, related_os_list)):
            return True

    return False


class _OsVariant(object):
    def __init__(self, o):
        self._os = o
        self._family = self._os and self._os.get_family() or None

        self.name = self._os and self._os.get_short_id() or "generic"
        self.label = self._os and self._os.get_name() or "Generic"

        self.sortby = self._get_sortby()
        self.urldistro = self._get_urldistro()
        self.supported = self._get_supported()


    ###############
    # Cached APIs #
    ###############

    def _get_sortby(self):
        if not self._os:
            return "1"

        version = self._os.get_version()
        try:
            t = version.split(".")
            t = t[:min(4, len(t))] + [0] * (4 - min(4, len(t)))
            new_version = ""
            for n in t:
                new_version = new_version + ("%.4i" % int(n))
            version = new_version
        except:
            pass

        distro = self._os.get_distro()
        return "%s-%s" % (distro, version)

    def _get_supported(self):
        if not self._os:
            return True
        d = self._os.get_eol_date_string()
        name = self._os.get_short_id()

        if d:
            return (datetime.datetime.strptime(d, "%Y-%m-%d") >
                    datetime.datetime.now())

        # As of libosinfo 2.11, many clearly EOL distros don't have an
        # EOL date. So assume None == EOL, add some manual work arounds.
        # We should fix this in a new libosinfo version, and then drop
        # this hack
        if name in ["rhel7.0", "rhel7.1", "fedora19", "fedora20", "fedora21",
            "debian6", "debian7", "ubuntu13.04", "ubuntu13.10", "ubuntu14.04",
            "ubuntu14.10", "win8", "win8.1", "win2k12", "win2k12r2"]:
            return True
        return False

    def _get_urldistro(self):
        if not self._os:
            return None
        urldistro = self._os.get_distro()
        remap = {
            "opensuse" : "suse",
            "sles" : "suse",
            "mes" : "mandriva"
        }

        if remap.get(urldistro):
            return remap[urldistro]

        return urldistro


    ########################
    # Internal helper APIs #
    ########################

    def _is_related_to(self, related_os_list):
        if not self._os:
            return False
        return _is_os_related_to(self._os, related_os_list)


    ###############
    # Public APIs #
    ###############

    def get_typename(self):
        """
        Streamline the family name for use in the virt-manager UI
        """
        if not self._os:
            return "generic"

        if self._family in ['linux']:
            return "linux"

        if self._family in ['win9x', 'winnt', 'win16']:
            return "windows"

        if self._family in ['solaris']:
            return "solaris"

        if self._family in ['openbsd', 'freebsd', 'netbsd']:
            return "unix"

        return "other"

    def is_windows(self):
        return self.get_typename() == "windows"

    def need_old_xen_disable_acpi(self):
        return self._is_related_to(["winxp", "win2k"])

    def get_clock(self):
        if self.is_windows() or self._family in ['solaris']:
            return "localtime"
        return "utc"

    def supports_virtioconsole(self):
        # We used to enable this for Fedora 18+, because systemd would
        # autostart a getty on /dev/hvc0 which made 'virsh console' work
        # out of the box for a login prompt. However now in Fedora
        # virtio-console is compiled as a module, and systemd doesn't
        # detect it in time to start a getty. So the benefit of using
        # it as the default is erased, and we reverted to this.
        # https://bugzilla.redhat.com/show_bug.cgi?id=1039742
        return False

    def supports_virtiommio(self):
        return self._is_related_to(["fedora19"])

    def supports_acpi(self, default):
        if self._family in ['msdos']:
            return False
        return default

    def supports_apic(self, default):
        return self.supports_acpi(default)

    def default_netmodel(self):
        """
        Default non-virtio net-model, since we check for that separately
        """
        if not self._os:
            return None

        fltr = libosinfo.Filter()
        fltr.add_constraint("class", "net")
        devs = self._os.get_all_devices(fltr)
        for idx in range(devs.get_length()):
            devname = devs.get_nth(idx).get_name()
            if devname != "virtio-net":
                return devname
        return None

    def default_inputtype(self):
        if self._os:
            fltr = libosinfo.Filter()
            fltr.add_constraint("class", "input")
            devs = self._os.get_all_devices(fltr)
            if devs.get_length():
                return devs.get_nth(0).get_name()
        return "mouse"

    def default_inputbus(self):
        if self._os:
            fltr = libosinfo.Filter()
            fltr.add_constraint("class", "input")
            devs = self._os.get_all_devices(fltr)
            if devs.get_length():
                return devs.get_nth(0).get_bus_type()
        return "ps2"

    def supports_virtiodisk(self):
        if not self._os:
            return False

        if self._os.get_distro() == "fedora":
            if self._os.get_version() == "unknown":
                return False
            return int(self._os.get_version()) >= 10

        fltr = libosinfo.Filter()
        fltr.add_constraint("class", "block")
        devs = self._os.get_all_devices(fltr)
        for dev in range(devs.get_length()):
            d = devs.get_nth(dev)
            if d.get_name() == "virtio-block":
                return True

        return False

    def supports_virtionet(self):
        if not self._os:
            return False

        if self._os.get_distro() == "fedora":
            if self._os.get_version() == "unknown":
                return False
            return int(self._os.get_version()) >= 9

        fltr = libosinfo.Filter()
        fltr.add_constraint("class", "net")
        devs = self._os.get_all_devices(fltr)
        for dev in range(devs.get_length()):
            d = devs.get_nth(dev)
            if d.get_name() == "virtio-net":
                return True
        return False

    def supports_qemu_ga(self):
        if not self._os:
            return False

        if self.name.split(".")[0] in ["rhel7", "rhel6", "centos7", "centos6"]:
            return True

        if self._os.get_distro() == "fedora":
            if self._os.get_version() == "unknown":
                return False
            return int(self._os.get_version()) >= 18

        return False

    def default_videomodel(self, guest):
        if guest.os.is_ppc64() and guest.os.machine == "pseries":
            return "vga"

        # Marc Deslauriers of canonical had previously patched us
        # to use vmvga for ubuntu, see fb76c4e5. And Fedora users report
        # issues with ubuntu + qxl for as late as 14.04, so carry the vmvga
        # default forward until someone says otherwise. In 2014-09 I contacted
        # Marc offlist and he said this was fine for now.
        if self._os and self._os.get_distro() == "ubuntu":
            return "vmvga"

        if guest.has_spice() and guest.os.is_x86():
            return "qxl"

        if self.is_windows():
            return "vga"

        return None

    def get_recommended_resources(self, guest):
        ret = {}
        def read_resource(resources, minimum, arch):
            # If we are reading the "minimum" block, allocate more
            # resources.
            ram_scale = minimum and 2 or 1
            n_cpus_scale = minimum and 2 or 1
            storage_scale = minimum and 2 or 1
            for i in range(resources.get_length()):
                r = resources.get_nth(i)
                if r.get_architecture() == arch:
                    ret["ram"] = r.get_ram() * ram_scale
                    ret["cpu"] = r.get_cpu()
                    ret["n-cpus"] = r.get_n_cpus() * n_cpus_scale
                    ret["storage"] = r.get_storage() * storage_scale
                    break

        # libosinfo may miss the recommended resources block for some OS,
        # in this case read first the minimum resources (if present)
        # and use them.
        read_resource(self._os.get_minimum_resources(), True, "all")
        read_resource(self._os.get_minimum_resources(), True, guest.os.arch)
        read_resource(self._os.get_recommended_resources(), False, "all")
        read_resource(self._os.get_recommended_resources(),
            False, guest.os.arch)

        # machvirt doesn't allow smp in non-kvm mode
        if guest.type != "kvm" and guest.os.is_arm_machvirt():
            ret["n-cpus"] = 1

        return ret

OSDB = _OSDB()
